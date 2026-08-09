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
#                [--interval 60] [--worktree <dir>]
#
# The state file is the loop's memory of what has been seen. Seed it with rows
# of `<owner/repo> <number> <sha> <ref>` to baseline heads as already reviewed;
# an empty file means every open pull request reports as new, which is the
# right default when the loop is establishing itself.
#
# Tracks up to 200 open pull requests per repository. That is a documented
# property rather than an accident: past the limit a tracked pull request would
# be missing from the answer and read as closed.

set -uo pipefail

REPOS=""; STATE=""; INTERVAL=60; WORKTREE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --repos)    REPOS="${2:-}"; shift 2 ;;
    --state)    STATE="${2:-}"; shift 2 ;;
    --interval) INTERVAL="${2:-60}"; shift 2 ;;
    --worktree) WORKTREE="${2:-}"; shift 2 ;;
    *) echo "watch-prs.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$REPOS" ] || { echo "watch-prs.sh: --repos is required" >&2; exit 2; }
[ -n "$STATE" ] || { echo "watch-prs.sh: --state is required" >&2; exit 2; }
touch "$STATE" 2>/dev/null || { echo "watch-prs.sh: cannot write state file: $STATE" >&2; exit 2; }

REPO_LIST=$(printf '%s' "$REPOS" | tr ',' ' ')

prev_branch=""
[ -n "$WORKTREE" ] && prev_branch=$(git -C "$WORKTREE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

while true; do
  new_state=""

  for repo in $REPO_LIST; do
    # A failed query must never look like "everything closed". On error, carry
    # this repo's rows forward untouched and try again next cycle — otherwise a
    # network blip reports every tracked pull request as closed.
    # --limit is not optional here. `gh pr list` defaults to 30, and a tracked
    # pull request beyond that page is simply absent from the answer — which
    # the closure check below cannot tell apart from closed, so it would retire
    # a live pull request and never mention it again. Same failure as the
    # nested-guard bug, reached through a different door.
    if ! out=$(gh pr list --repo "$repo" --state open --limit 200 \
                 --json number,headRefOid,headRefName \
                 --jq '.[] | "\(.number) \(.headRefOid) \(.headRefName)"' 2>/dev/null); then
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
