#!/usr/bin/env bash
#
# Link this repo's config into ~/.claude and ~/.codex.
#
#   ./install.sh          create or repair every link
#   ./install.sh status    report what is linked, missing, or drifted
#
# Idempotent: re-running it is always safe. An existing regular file at a
# target is moved aside to <target>.bak.<timestamp> before being replaced,
# so nothing is destroyed.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

# An optional sibling repo holding machine-local configuration, linked when it
# exists. Claude reads both halves without either file referencing the other:
# the shared prompt goes to ~/CLAUDE.md, which Claude finds by walking up from
# the working directory, and the private one to ~/.claude/CLAUDE.md at user
# scope. Codex has neither mechanism, so it gets the shared file alone.
PRIVATE="${AGENT_CONFIG_PRIVATE:-$(dirname "$REPO")/agent-config-private}"

# Format: <repo path>|<target>. Directories are linked whole, so a file added
# later is picked up with no re-run.
#
# That includes ~/.codex/skills, where Codex materializes its own built-in
# skills into .system. It writes them into this repo, which .gitignore covers;
# it leaves everything else in the directory alone, tested rather than assumed.
links=(
  "$REPO/AGENTS.md|$HOME/CLAUDE.md"
  "$REPO/AGENTS.md|$CODEX_HOME/AGENTS.md"
  "$REPO/skills|$CLAUDE_HOME/skills"
  "$REPO/skills|$CODEX_HOME/skills"
  "$REPO/claude/agents|$CLAUDE_HOME/agents"
  "$REPO/claude/commands|$CLAUDE_HOME/commands"
  "$REPO/codex/prompts|$CODEX_HOME/prompts"
)

if [ -d "$PRIVATE" ]; then
  links+=(
    "$PRIVATE/claude/CLAUDE.md|$CLAUDE_HOME/CLAUDE.md"
    "$PRIVATE/claude/settings.json|$CLAUDE_HOME/settings.json"
    "$PRIVATE/claude/statusline.sh|$CLAUDE_HOME/statusline.sh"
    "$PRIVATE/codex/config.toml|$CODEX_HOME/config.toml"
  )
fi

# Prints one of: ok, missing, wrong-link, no-source, or drifted (a real file
# where we want a link — most likely a tool rewrote the file instead of
# following the symlink).
#
# no-source comes first because a link to a file that isn't there still reads
# as a link: without this check a missing source is linked anyway, and both
# install and status call the result ok while the config silently delivers
# nothing.
state() {
  local src="$1" dst="$2"
  if [ ! -e "$src" ]; then
    echo no-source
  elif [ -L "$dst" ]; then
    [ "$(readlink "$dst")" = "$src" ] && echo ok || echo wrong-link
  elif [ -e "$dst" ]; then
    echo drifted
  else
    echo missing
  fi
}

cmd_status() {
  local rc=0
  for entry in "${links[@]}"; do
    local src="${entry%%|*}" dst="${entry##*|}"
    local s; s="$(state "$src" "$dst")"
    printf '%-10s %s\n' "$s" "${dst/#$HOME/~}"
    [ "$s" = ok ] || rc=1
  done
  if [ $rc -ne 0 ]; then
    echo
    echo "Run ./install.sh to create or repair these."
    echo "A 'drifted' entry means a tool replaced the symlink with a real file;"
    echo "check whether it holds changes worth keeping before re-linking."
  fi
  return $rc
}

cmd_install() {
  local stamp; stamp="$(date +%Y%m%d%H%M%S)"
  for entry in "${links[@]}"; do
    local src="${entry%%|*}" dst="${entry##*|}"
    local s; s="$(state "$src" "$dst")"
    case "$s" in
      ok) printf '%-10s %s\n' "ok" "${dst/#$HOME/~}"; continue ;;
      no-source)
        printf '%-10s %s (nothing at %s)\n' "skipped" "${dst/#$HOME/~}" "${src/#$HOME/~}"
        rc=1; continue ;;
      drifted)
        mv "$dst" "$dst.bak.$stamp"
        printf '%-10s %s\n' "backed-up" "${dst/#$HOME/~}.bak.$stamp"
        ;;
      wrong-link) rm "$dst" ;;
    esac
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
    printf '%-10s %s -> %s\n' "linked" "${dst/#$HOME/~}" "${src/#$HOME/~}"
  done
}

case "${1:-install}" in
  status) cmd_status ;;
  install) cmd_install ;;
  *) echo "usage: $0 [install|status]" >&2; exit 64 ;;
esac
