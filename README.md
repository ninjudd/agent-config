# agent-config

My global instructions and skills for Claude Code and Codex, in one place with
a real history. Both tools read them through symlinks created by `install.sh`,
so editing a file here changes live behaviour immediately — there is no build
or sync step.

```sh
git clone git@github.com:ninjudd/agent-config.git
./agent-config/install.sh          # create or repair every link
./agent-config/install.sh status   # report what is linked, missing, or drifted
```

## What's here

| Path | Linked to | Read by |
|------|-----------|---------|
| `AGENTS.md` | `~/CLAUDE.md`, `~/.codex/AGENTS.md` | both |
| `skills/` | `~/.claude/skills`, `~/.codex/skills` | both |
| `claude/agents/` | `~/.claude/agents` | Claude Code |
| `claude/commands/` | `~/.claude/commands` | Claude Code |
| `codex/prompts/` | `~/.codex/prompts` | Codex |

`AGENTS.md` is the prompt: rules that apply in every repository, so a project's
own `AGENTS.md` only has to carry what is specific to it.

## The private half

Machine-local configuration — settings, a status line, and instructions about
directories that exist on one laptop — lives in a separate private repo.
`install.sh` picks it up when it sits alongside this one, or wherever
`AGENT_CONFIG_PRIVATE` points:

```
~/ninjudd/agent-config          # this repo
~/ninjudd/agent-config-private  # optional, linked automatically
```

Neither half references the other. Claude Code reads both because they arrive
through different mechanisms: the shared prompt is linked to `~/CLAUDE.md`,
which Claude finds by walking up from the working directory, and the private
one to `~/.claude/CLAUDE.md` at user scope. Discovered files are concatenated
rather than overriding each other, so both land in context and each stays
editable at its source, with no import, no assembly, and no generated file.

The one limit worth knowing: `~/CLAUDE.md` is found by walking up from the
working directory, so it loads for anything under `$HOME` and not for a
repository checked out elsewhere, such as `/opt` or a temp directory.

Codex is pointed at `AGENTS.md` alone and never sees the private half. It has
no equivalent mechanism — three plausible workarounds are each ruled out by its
documented behaviour:

- **No import syntax.** "The design prioritizes hierarchical overrides rather than file inclusion."
- **`AGENTS.override.md` replaces rather than merges.** "Codex uses only the first non-empty file at this level" — so putting the shared rules in one slot and the private ones in the other silently drops the shared rules.
- **Discovery never rises above the git root.** "Starting at the project root (typically the Git root), Codex walks down to your current working directory" — so the `~/CLAUDE.md` trick has no Codex equivalent, and a shared file in a parent directory is invisible.

Giving Codex both halves would mean generating a combined file. Not worth it
for guidance about a directory Codex is never pointed at.

## Why directories are linked whole

Linking a whole directory rather than each file inside it means a file added
later is picked up with no re-run, by both tools at once — `claude plugin init`
scaffolds straight into `skills/` here, already under version control.

That includes `~/.codex/skills`, even though Codex manages that directory: it
materializes its own built-in skills into `.system` there, which is to say into
this repo. `.gitignore` covers `/skills/.system/`, and they ship with Codex, so
losing them costs nothing — the next session writes them back. What matters is
that Codex leaves everything *else* in the directory alone, which was tested
rather than assumed: a user skill and a dotfile both survived a session that
recreated all six built-ins around them.

Directories holding only a `.README.md` are placeholders, wired up and empty.
The dot matters: a plain `README.md` in `commands/` becomes a `/README` slash
command, and one in `agents/` gets parsed as an agent definition.

## Drift

Both tools write to their own settings — toggling a plugin rewrites
`settings.json`, adding an MCP server rewrites `config.toml`. Both were tested
against a symlinked file in a throwaway config directory, and both write
*through* the link: the symlink survived and the change landed in the repo as a
normal diff.

So drift is not a live problem, but `./install.sh status` still checks for it,
because nothing guarantees that behaviour across versions and the failure is
silent — a tool that replaced the file atomically instead would leave the repo
stale with no error. A `drifted` entry means exactly that happened; check
whether the real file holds changes worth keeping before re-running
`./install.sh`, which moves it aside to `.bak.<timestamp>` rather than deleting
it.
