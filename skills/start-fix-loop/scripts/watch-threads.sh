#!/usr/bin/env bash
# watch-threads.sh — emit one line per piece of outstanding review work across
# every open pull request in one or more GitHub repositories. Silent when
# nothing is outstanding. Intended to run under Claude Code's `Monitor` with
# `persistent: true`, where each stdout line becomes one notification.
#
#   FINDING   an unresolved review thread that has not been announced recently
#   VERDICT   a pull request sitting at CHANGES_REQUESTED, thread or no thread
#   REVIEW    a submitted review carrying a body without a verdict — the shape
#             Codex and Bugbot post, which never moves reviewDecision
#
# This watch is deliberately **level-triggered**: it reports what is currently
# unresolved rather than what just changed. An edge-triggered watch loses a
# finding permanently the one time it misses an edge — a thread posted while
# the watcher was starting, or during a network blip, is never "new" again and
# would go unmentioned forever. Re-announcing is the cheaper failure.
#
# Usage:
#   watch-threads.sh --repos owner/a[,owner/b...] --state <path>
#                    [--interval 60] [--renotify 900]
#
# --renotify is how many seconds before a still-unresolved thread is announced
# again. Set it high enough to be a reminder rather than a stream.

set -uo pipefail

REPOS=""; STATE=""; INTERVAL=60; RENOTIFY=900

while [ $# -gt 0 ]; do
  case "$1" in
    --repos)    REPOS="${2:-}"; shift 2 ;;
    --state)    STATE="${2:-}"; shift 2 ;;
    --interval) INTERVAL="${2:-60}"; shift 2 ;;
    --renotify) RENOTIFY="${2:-900}"; shift 2 ;;
    *) echo "watch-threads.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$REPOS" ] || { echo "watch-threads.sh: --repos is required" >&2; exit 2; }
[ -n "$STATE" ] || { echo "watch-threads.sh: --state is required" >&2; exit 2; }
touch "$STATE" 2>/dev/null || { echo "watch-threads.sh: cannot write state file: $STATE" >&2; exit 2; }

# The skill's own floor: never poll GitHub harder than every 30 seconds.
[ "$INTERVAL" -lt 30 ] 2>/dev/null && INTERVAL=30

REPO_LIST=$(printf '%s' "$REPOS" | tr ',' ' ')

while true; do
  now=$(date +%s)
  new_state=""

  for slug in $REPO_LIST; do
    owner="${slug%%/*}"; name="${slug##*/}"

    # A failed query must not be read as "nothing outstanding". Carry this
    # repo's rows forward so a blip cannot silently retire a live finding.
    # --limit is not optional: `gh pr list` defaults to 30, and pull requests
    # past that page are never scanned, so their findings are never announced
    # at all. Scans threads for up to 200 open pull requests per repository;
    # the verdict query below paginates instead and has no such ceiling, so
    # the 200 is this listing's limit and not the script's.
    if ! prs=$(gh pr list --repo "$slug" --state open --limit 200 --json number --jq '.[].number' 2>/dev/null); then
      carried=$(grep " $slug " "$STATE" 2>/dev/null || true)
      [ -n "$carried" ] && new_state="$new_state$carried
"
      continue
    fi

    # A verdict is outstanding work even with no thread attached to it. A
    # reviewer may put every finding in the review summary body and open no
    # inline thread at all, and then the thread query below is correctly
    # silent while the pull request sits blocked at CHANGES_REQUESTED. Watching
    # threads alone reads that as "nothing outstanding", which is the one
    # reading that must never be wrong. Asked per repository rather than per
    # pull request, because one query answers for all of them.
    # Paginated, and it has to be: GraphQL connections cap `first` at 100 —
    # `first:200` is rejected outright as EXCESSIVE_PAGINATION — so a single
    # page would watch verdicts for 100 pull requests while the thread query
    # above covers 200. That asymmetry fails in the worst available direction.
    # A pull request past the page still has its threads watched, so a review
    # with inline findings is still seen; the one lost is a review whose
    # findings live only in the summary body, which is precisely the case this
    # query exists to catch. `orderBy` is pinned so the traversal is stable
    # across pages rather than arbitrary.
    #
    # Ask `reviews(states:[CHANGES_REQUESTED])` rather than `latestReviews`.
    # `latestReviews` is the most recent review *per author* whatever its
    # state, and replying inside a thread files a COMMENTED review — so a
    # reviewer answering their own thread displaces their standing changes
    # request out of that connection while `reviewDecision` stays
    # CHANGES_REQUESTED. The pull request would pass the outer filter, match
    # nothing inside, and emit nothing: a false negative in exactly the case
    # this query exists to catch, and one that correlates with discussion, so
    # it goes quiet on the pull requests being argued about and stays loud on
    # the ones nobody has touched. `last:1` is one line per pull request
    # rather than per author, which is what the skill documents.
    if ! verdicts=$(gh api graphql --paginate -f query='
      query($o:String!,$r:String!,$endCursor:String){ repository(owner:$o,name:$r){
        pullRequests(states:OPEN, first:100, after:$endCursor,
                     orderBy:{field:CREATED_AT, direction:ASC}){
          pageInfo{ hasNextPage endCursor }
          nodes{
            number reviewDecision
            reviews(states:[CHANGES_REQUESTED], last:1){ nodes{
              author{login} body commit{oid} } } } } } }' \
      -f o="$owner" -f r="$name" \
      --jq '.data.repository.pullRequests.nodes[]
            | select(.reviewDecision == "CHANGES_REQUESTED")
            | . as $pr | .reviews.nodes[]
            | "\($pr.number)\t\(.author.login)\t\(.commit.oid)\t\(.body // "" | gsub("[\r\n]+"; " ") | .[0:130])"' \
      2>/dev/null); then
      carried=$(awk -v s="$slug" '$1 ~ /^verdict:/ && $2==s' "$STATE" 2>/dev/null || true)
      [ -n "$carried" ] && new_state="$new_state$carried
"
    else
      while IFS=$'\t' read -r vn vwho vsha vsnip; do
        [ -n "${vn:-}" ] || continue
        # Keyed on author and reviewed SHA, so a re-review of a new head is a
        # new row and announces immediately rather than waiting out --renotify.
        vid="verdict:$vwho:$vsha"
        last=$(awk -v t="$vid" '$1==t {print $4}' "$STATE" 2>/dev/null)
        if [ -z "$last" ]; then
          echo "VERDICT $slug#$vn CHANGES_REQUESTED on ${vsha:0:8} [$vwho] — $vsnip"
          last=$now
        elif [ $((now - last)) -ge "$RENOTIFY" ]; then
          echo "VERDICT (still open) $slug#$vn CHANGES_REQUESTED on ${vsha:0:8} [$vwho] — $vsnip"
          last=$now
        fi
        new_state="$new_state$vid $slug $vn $last
"
      done <<EOF
$verdicts
EOF
    fi

    for n in $prs; do
      if ! threads=$(gh api graphql -f query='
        query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){
          pullRequest(number:$n){ reviewThreads(first:100){ nodes{
            id isResolved path line
            comments(last:1){nodes{author{login} body}} } } } } }' \
        -f o="$owner" -f r="$name" -F n="$n" \
        --jq '.data.repository.pullRequest.reviewThreads.nodes[]
              | select(.isResolved == false)
              | "\(.id)\t\(.path):\(.line // "?")\t\(.comments.nodes[0].author.login // "?")\t\(.comments.nodes[0].body // "" | gsub("[\r\n]+"; " ") | .[0:130])"' \
        2>/dev/null); then
        # The same rule as the repo-level guard, for the same reason, and it is
        # the case that falls between them: the repo query answered but this
        # one did not. Dropping this pull request's rows would blank every one
        # of its threads' last-announced stamps, so next cycle they all
        # re-announce as fresh findings at --interval rather than --renotify.
        # That is a flood, on a repository whose API is already flaky, and
        # Monitor stops a watcher that produces too many events — leaving the
        # fix loop deaf while its skill reads silence as "nothing outstanding".
        # Thread rows only. This repository's verdict rows were already
        # rebuilt above, so carrying them again here would duplicate them.
        carried=$(awk -v s="$slug" -v p="$n" '$1 !~ /^(verdict:|review:)/ && $2==s && $3==p' "$STATE" 2>/dev/null || true)
        [ -n "$carried" ] && new_state="$new_state$carried
"
        continue
      fi

      while IFS=$'\t' read -r tid loc who snip; do
        [ -n "${tid:-}" ] || continue
        last=$(awk -v t="$tid" '$1==t {print $4}' "$STATE" 2>/dev/null)
        if [ -z "$last" ]; then
          echo "FINDING $slug#$n $loc [$who] — $snip"
          last=$now
        elif [ $((now - last)) -ge "$RENOTIFY" ]; then
          echo "FINDING (still open) $slug#$n $loc [$who] — $snip"
          last=$now
        fi
        new_state="$new_state$tid $slug $n $last
"
      done <<EOF
$threads
EOF

      # A review can carry findings and still never be a verdict. Codex and
      # Bugbot submit COMMENTED reviews, so reviewDecision never moves and the
      # verdict query is blind to them; their findings are seen only when they
      # arrive as inline threads, and a body-only review — a failed anchor, a
      # summary with no thread under it — would otherwise vanish without a
      # trace. REST rather than GraphQL, and per pull request rather than per
      # repository, because a reviews connection can only be windowed and the
      # window is exactly the trap: every reply the fix loop posts inside a
      # thread files an empty COMMENTED review, so `last:10` returns ten
      # replies and the bot review has been displaced — the latestReviews
      # failure again, one query over. One line per review, keyed on author
      # and reviewed SHA the way verdicts are. Never re-announced: a COMMENTED
      # review has no resolved state to clear, so "(still open)" would be a
      # reminder with no off switch. Bodies empty once HTML comments are
      # stripped are skipped, which is also what keeps the loop's own replies
      # from coming back to it as work.
      if ! reviews=$(gh api "repos/$slug/pulls/$n/reviews" --paginate \
        --jq '.[] | select(.state == "COMMENTED")
              | (.body // "" | gsub("<!--([^-]|-[^-]|--[^>])*-->"; "") | gsub("<[^>]*>"; "") | gsub("[\r\n]+"; " ")) as $body
              | select(($body | gsub("[[:space:]]+"; "")) != "")
              | "\(.user.login)\t\(.commit_id)\t\($body[0:130])"' \
        2>/dev/null); then
        carried=$(awk -v s="$slug" -v p="$n" '$1 ~ /^review:/ && $2==s && $3==p' "$STATE" 2>/dev/null || true)
        [ -n "$carried" ] && new_state="$new_state$carried
"
      else
        while IFS=$'\t' read -r cwho csha csnip; do
          [ -n "${cwho:-}" ] || continue
          cid="review:$cwho:$csha"
          last=$(awk -v t="$cid" '$1==t {print $4}' "$STATE" 2>/dev/null)
          if [ -z "$last" ]; then
            echo "REVIEW $slug#$n by [$cwho] on ${csha:0:8} — $csnip"
            last=$now
          fi
          new_state="$new_state$cid $slug $n $last
"
        done <<REVEOF
$reviews
REVEOF
      fi
    done
  done

  # Rows are `<threadId> <owner/repo> <pr> <lastAnnouncedEpoch>`. Rebuilt each
  # cycle from what is currently unresolved, so a thread that got resolved
  # simply falls out. Rows are only ever carried forward for a query that
  # failed — the repository listing, or one pull request's threads — never for
  # one that answered.
  printf '%s' "$new_state" | grep -v '^[[:space:]]*$' > "$STATE.tmp" 2>/dev/null
  mv "$STATE.tmp" "$STATE" 2>/dev/null

  sleep "$INTERVAL"
done
