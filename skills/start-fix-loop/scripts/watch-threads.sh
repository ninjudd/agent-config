#!/usr/bin/env bash
# watch-threads.sh — emit one line per unresolved review thread across every
# open pull request in one or more GitHub repositories. Silent when nothing is
# outstanding. Intended to run under Claude Code's `Monitor` with
# `persistent: true`, where each stdout line becomes one notification.
#
#   FINDING   an unresolved review thread that has not been announced recently
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
    if ! prs=$(gh pr list --repo "$slug" --state open --json number --jq '.[].number' 2>/dev/null); then
      carried=$(grep " $slug " "$STATE" 2>/dev/null || true)
      [ -n "$carried" ] && new_state="$new_state$carried
"
      continue
    fi

    for n in $prs; do
      threads=$(gh api graphql -f query='
        query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){
          pullRequest(number:$n){ reviewThreads(first:100){ nodes{
            id isResolved path line
            comments(last:1){nodes{author{login} body}} } } } } }' \
        -f o="$owner" -f r="$name" -F n="$n" \
        --jq '.data.repository.pullRequest.reviewThreads.nodes[]
              | select(.isResolved == false)
              | "\(.id)\t\(.path):\(.line // "?")\t\(.comments.nodes[0].author.login // "?")\t\(.comments.nodes[0].body // "" | gsub("[\r\n]+"; " ") | .[0:130])"' \
        2>/dev/null) || continue

      while IFS=$'\t' read -r tid loc who snip; do
        [ -n "${tid:-}" ] || continue
        last=$(awk -v t="$tid" '$1==t {print $3}' "$STATE" 2>/dev/null)
        if [ -z "$last" ]; then
          echo "FINDING $slug#$n $loc [$who] — $snip"
          last=$now
        elif [ $((now - last)) -ge "$RENOTIFY" ]; then
          echo "FINDING (still open) $slug#$n $loc [$who] — $snip"
          last=$now
        fi
        new_state="$new_state$tid $slug $last
"
      done <<EOF
$threads
EOF
    done
  done

  # Rebuilt from what is currently unresolved, so a thread that got resolved
  # simply falls out. Rows are only ever carried forward for a repo whose query
  # failed, never for one that answered.
  printf '%s' "$new_state" | grep -v '^[[:space:]]*$' > "$STATE.tmp" 2>/dev/null
  mv "$STATE.tmp" "$STATE" 2>/dev/null

  sleep "$INTERVAL"
done
