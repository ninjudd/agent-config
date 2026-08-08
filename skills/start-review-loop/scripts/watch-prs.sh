#!/usr/bin/env bash
# watch-prs.sh — emit one line per reviewable event across one or more GitHub
# repositories, and stay silent otherwise. Intended to run under Claude Code's
# `Monitor` with `persistent: true`, where each stdout line becomes one
# notification.
#
#   NEW PR    a pull request opened that the state file has not seen
#   NEW HEAD  a tracked pull request's head SHA moved
#   CLOSED    a tracked pull request left the open set
#   BRANCH    the watched worktree changed branch
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

    while read -r num sha ref; do
      [ -n "$num" ] || continue
      known=$(awk -v r="$repo" -v n="$num" '$1==r && $2==n {print $3}' "$STATE" 2>/dev/null)
      if [ -z "$known" ]; then
        echo "NEW PR $repo#$num ($ref) head=${sha:0:7} — unreviewed, needs an exact-head review"
      elif [ "$known" != "$sha" ]; then
        echo "NEW HEAD $repo#$num ($ref): ${known:0:7} -> ${sha:0:7} — needs an exact-head review"
      fi
      new_state="$new_state$repo $num $sha $ref
"
    done <<EOF
$out
EOF

    # Closure detection is deliberately NOT nested inside a "did we get any
    # open pull requests" check. Closing the last open one is precisely the
    # case that produces an empty list, and guarding this on a non-empty list
    # swallows it silently.
    while read -r krepo knum ksha kref; do
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
