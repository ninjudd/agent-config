#!/usr/bin/env bash
# watch-prs.sh — emit one line per reviewable event across one or more GitHub
# repositories, and stay silent otherwise. Intended to run under Claude Code's
# `Monitor` with `persistent: true`, where each stdout line becomes one
# notification.
#
#   NEW PR     a pull request opened that the state file has not seen
#   NEW HEAD   a tracked pull request's head SHA moved
#   RESPONDED  still CHANGES_REQUESTED, every thread resolved, head unchanged —
#              the author answered without pushing, so no head event is coming.
#              Once per head, and never alongside NEW PR or NEW HEAD, which
#              already say to review that head.
#   CLOSED     a tracked pull request left the open set
#   BRANCH     the watched worktree changed branch
#
# Usage:
#   watch-prs.sh --repos owner/a[,owner/b...] --state <path>
#                [--author login[,login...]] [--interval 60] [--worktree <dir>]
#
# --author narrows the watch to pull requests those logins authored, which is
# how the review loop keeps to the operator's own on a shared repository. Pass
# logins literally, never `@me`: `@me` is resolved against whichever token is
# live when the query runs, and under the review loop's GH_TOKEN that is the
# reviewing account, which authors nothing — the watch would then be silent
# from the first pass on, indistinguishable from a repository with nothing
# open. Without the flag every open pull request is watched. This watcher
# filters at the source where watch-threads.sh deliberately does not, because
# its events are pushes: on a shared repository every push by anyone is one,
# none of them is the loop's to review, and every line here is a Monitor
# notification counting toward the limit that stops a watcher.
#
# The state file is the loop's memory of what has been seen. Seed it with rows
# of `<owner/repo> <number> <sha> <ref>` to baseline heads as already reviewed;
# an empty file means every watched pull request reports as new, which is the
# right default when the loop is establishing itself. The state file belongs
# to one scope: narrowing --author against an existing one reports the pull
# requests that left the watch as CLOSED once, so start a fresh file when the
# scope changes.
#
# Tracks up to 200 open pull requests per repository — per author, when
# --author is given, since each login is listed separately. That is a
# documented property rather than an accident: past the limit a tracked pull
# request would be missing from the answer and read as closed.

set -uo pipefail

REPOS=""; STATE=""; INTERVAL=60; WORKTREE=""; AUTHORS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --repos)    REPOS="${2:-}"; shift 2 ;;
    --state)    STATE="${2:-}"; shift 2 ;;
    --interval) INTERVAL="${2:-60}"; shift 2 ;;
    --worktree) WORKTREE="${2:-}"; shift 2 ;;
    --author)   AUTHORS="${2:-}"; shift 2 ;;
    *) echo "watch-prs.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$REPOS" ] || { echo "watch-prs.sh: --repos is required" >&2; exit 2; }
[ -n "$STATE" ] || { echo "watch-prs.sh: --state is required" >&2; exit 2; }
touch "$STATE" 2>/dev/null || { echo "watch-prs.sh: cannot write state file: $STATE" >&2; exit 2; }

REPO_LIST=$(printf '%s' "$REPOS" | tr ',' ' ')
AUTHOR_LIST=$(printf '%s' "$AUTHORS" | tr ',' ' ')

# A login that does not exist is not an error to `gh pr list --author`: it is
# an empty answer, exit 0, on every pass — a mistyped operator login would give
# a watch that starts cleanly and never says anything. Refuse it once, here,
# where the message is read. A real login that authors nothing is the same
# silence, and only the establishment count in the skill catches that.
#
# Say which failure it was. `gh api` exits non-zero for a network failure, a
# proxy, a rate limit or a bad token exactly as it does for a 404, and the
# skill tells its reader that establishment is the moment a wrong login
# announces itself — so "no such login" on a network blip sends them off to
# re-resolve a login that was right all along. Only a 404 is a missing login;
# everything else is the lookup failing, which still refuses to start, since
# nothing should run on an unverified login, but under its own name.
for a in $AUTHOR_LIST; do
  case "$a" in
    @*)    echo "watch-prs.sh: --author takes a literal login, not $a" >&2; exit 2 ;;
    app/*) probe="apps/${a#app/}" ;;   # `gh pr list --author app/dependabot`
    *)     probe="users/$a" ;;         # a user, or a bot as `dependabot[bot]`
  esac
  if ! err=$(gh api "$probe" 2>&1 >/dev/null); then
    case "$err" in
      *"HTTP 404"*) echo "watch-prs.sh: --author $a: no such GitHub login" >&2 ;;
      *) echo "watch-prs.sh: --author $a: could not verify login — network or auth error, not a missing login: ${err%%$'\n'*}" >&2 ;;
    esac
    exit 2
  fi
done

# One "<number> <sha> <ref>" line per open pull request in $1, restricted to
# $AUTHOR_LIST when that is set. Listed once per author rather than filtered
# client-side, so --limit bounds each author's pull requests rather than the
# repository's: on a repository with more than 200 open, a client-side filter
# over the first 200 would drop the operator's own past the cut, and those
# would read as closed. Any listing failing fails the whole call, so the
# caller carries the repository's rows forward instead of reading a partial
# answer as "everything else closed".
list_prs() {
  local repo="$1" a chunk out=""
  if [ -z "$AUTHOR_LIST" ]; then
    gh pr list --repo "$repo" --state open --limit 200 \
      --json number,headRefOid,headRefName \
      --jq '.[] | "\(.number) \(.headRefOid) \(.headRefName)"' 2>/dev/null
    return
  fi
  for a in $AUTHOR_LIST; do
    chunk=$(gh pr list --repo "$repo" --author "$a" --state open --limit 200 \
              --json number,headRefOid,headRefName \
              --jq '.[] | "\(.number) \(.headRefOid) \(.headRefName)"' 2>/dev/null) || return 1
    [ -n "$chunk" ] && out="$out$chunk
"
  done
  printf '%s' "$out"
}

prev_branch=""
[ -n "$WORKTREE" ] && prev_branch=$(git -C "$WORKTREE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

while true; do
  new_state=""

  for repo in $REPO_LIST; do
    # A failed query must never look like "everything closed". On error, carry
    # this repo's rows forward untouched and try again next cycle — otherwise a
    # network blip reports every tracked pull request as closed.
    # --limit is not optional in list_prs. `gh pr list` defaults to 30, and a
    # tracked pull request beyond that page is simply absent from the answer —
    # which the closure check below cannot tell apart from closed, so it would
    # retire a live pull request and never mention it again. Same failure as
    # the nested-guard bug, reached through a different door.
    if ! out=$(list_prs "$repo"); then
      carried=$(grep "^$repo " "$STATE" 2>/dev/null || true)
      [ -n "$carried" ] && new_state="$new_state$carried
"
      continue
    fi

    # A push is not the only thing this loop can be waiting on. A pull request
    # left at CHANGES_REQUESTED with every thread resolved is waiting on *us*:
    # the author answered, and a fix that produced no push — a body correction,
    # a reply, a declined finding — creates no new head for the check above to
    # notice. Nothing else will ever arrive, so watching heads alone deadlocks.
    # Asked once per repository; on failure every pull request's flag is simply
    # carried forward by the row rebuild below, and it retries next cycle.
    owner="${repo%%/*}"; name="${repo##*/}"
    # Paginated to match the 200 the header promises: GraphQL caps `first` at
    # 100 per page, so a single page would cover fewer pull requests than the
    # `gh pr list --limit 200` above and the two halves would disagree.
    # `orderBy` is pinned so the traversal is stable rather than arbitrary.
    responded=$(gh api graphql --paginate -f query='
      query($o:String!,$r:String!,$endCursor:String){ repository(owner:$o,name:$r){
        pullRequests(states:OPEN, first:100, after:$endCursor,
                     orderBy:{field:CREATED_AT, direction:ASC}){
          pageInfo{ hasNextPage endCursor }
          nodes{
            number reviewDecision
            reviewThreads(first:100){ nodes{ isResolved } } } } } }' \
      -f o="$owner" -f r="$name" \
      --jq '.data.repository.pullRequests.nodes[]
            | select(.reviewDecision == "CHANGES_REQUESTED")
            | select([.reviewThreads.nodes[] | select(.isResolved == false)] | length == 0)
            | "\(.number)"' 2>/dev/null || echo "__QUERYFAILED__")

    while read -r num sha ref; do
      [ -n "$num" ] || continue
      known=$(awk -v r="$repo" -v n="$num" '$1==r && $2==n {print $3}' "$STATE" 2>/dev/null)
      # Field 5 is the SHA a RESPONDED line was last emitted for, or "-".
      # Comparing it against the current head is what makes this fire once per
      # head: a re-review that requests changes again does not re-announce,
      # and a new push resets it because the row's SHA changed.
      flag=$(awk -v r="$repo" -v n="$num" '$1==r && $2==n {print $5}' "$STATE" 2>/dev/null)
      [ -n "$flag" ] || flag="-"
      if [ -z "$known" ]; then
        echo "NEW PR $repo#$num ($ref) head=${sha:0:7} — unreviewed, needs an exact-head review"
        # Announcing a head counts as having announced it, so the RESPONDED
        # test below suppresses a follow-up for it. Without this the head-
        # unchanged guard only defers the duplicate by one cycle: the row
        # rebuild writes this SHA into the state, so next cycle the guard
        # passes and RESPONDED fires about a head whose first review is
        # probably still running.
        flag="$sha"
      elif [ "$known" != "$sha" ]; then
        echo "NEW HEAD $repo#$num ($ref): ${known:0:7} -> ${sha:0:7} — needs an exact-head review"
        flag="$sha"
      fi
      # Only when the head is known and unchanged — that is, when neither of
      # the two events above fired for this pull request. RESPONDED exists for
      # the case where nothing was pushed, so emitting it beside NEW HEAD or
      # NEW PR would double the most frequent event in order to catch a rarer
      # one, and every line here is a Monitor notification that counts toward
      # the limit that stops a watcher.
      if [ "$responded" != "__QUERYFAILED__" ] && [ -n "$known" ] && [ "$known" = "$sha" ]; then
        if printf '%s\n' "$responded" | grep -qx "$num"; then
          if [ "$flag" != "$sha" ]; then
            echo "RESPONDED $repo#$num ($ref) head=${sha:0:7} — still CHANGES_REQUESTED with every thread resolved; re-review this head"
            flag="$sha"
          fi
        else
          flag="-"
        fi
      fi
      new_state="$new_state$repo $num $sha $ref $flag
"
    done <<EOF
$out
EOF

    # Closure detection is deliberately NOT nested inside a "did we get any
    # open pull requests" check. Closing the last open one is precisely the
    # case that produces an empty list, and guarding this on a non-empty list
    # swallows it silently.
    while read -r krepo knum ksha kref kflag; do
      [ "${krepo:-}" = "$repo" ] || continue
      if ! printf '%s\n' "$out" | grep -q "^$knum "; then
        echo "CLOSED $repo#$knum (${kref:-?}) — no longer open, dropping from the tracked set"
      fi
    done < "$STATE"
  done

  printf '%s' "$new_state" | grep -v '^[[:space:]]*$' > "$STATE.tmp" 2>/dev/null
  mv "$STATE.tmp" "$STATE" 2>/dev/null

  if [ -n "$WORKTREE" ]; then
    b=$(git -C "$WORKTREE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    if [ -n "$b" ] && [ "$b" != "$prev_branch" ]; then
      echo "BRANCH $WORKTREE: ${prev_branch:-?} -> $b — look for an open PR on it"
      prev_branch="$b"
    fi
  fi

  sleep "$INTERVAL"
done
