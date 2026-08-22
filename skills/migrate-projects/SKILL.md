---
name: migrate-projects
description: Migrate a repository from now.md, next.md, later.md, and all/ project plans into Projector's permanent directory format. Use only for the legacy project convention, not for ordinary project edits.
---

# Migrate Projects

Move legacy plans without guessing about ambiguous status or silently losing
inbound references.

## Plan the migration

Read the repository instructions and run the bundled planner from the
repository root:

```sh
python3 <skill-directory>/scripts/migrate_projects.py --root .
```

The dry run inventories every legacy entry point, combines list membership and
frontmatter, and reports the destination and new status. It exits with status
65 when a project belongs to multiple lists, has an unknown lifecycle value,
has neither a recognized value nor list membership, or would overwrite a
destination. Review every proposed `project`, `reference`, and `remove`
action before applying it.

The mapping is deliberate:

- `Shipped`, `Superseded`, and `Abandoned` become `done`, with the
  precise outcome retained in the plan body.
- `Reference` documents move to ordinary `docs/` and leave the project
  lifecycle.
- List membership maps remaining work to `now`, `next`, or `later`.
- Without list membership, `Active` and `Blocked` become `now`; `Draft`
  and `Stalled` become `later`.

## Apply and verify

Require a completely clean repository and an installed `projector` executable,
then run:

```sh
python3 <skill-directory>/scripts/migrate_projects.py --root . --apply
projector check
rg -n 'docs/projects/all|\]\(all/' .
command grep -rl 'docs/projects/all\|](all/' .
git diff --check
```

Application refuses symlinks in the legacy tree, uses `git mv` for history,
rewrites path-boundary-anchored inbound references in tracked files (including
files containing NUL bytes), repairs relative Markdown links, stages the new
convention document, and removes the three list files only after every project
has a disposition. A failure rolls the clean worktree back to its starting
commit. The final `command grep -rl` is required even when `rg` finds nothing
because `rg` skips binary-classified Markdown.

Inspect `git status` and the full diff. Do not commit, push, or merge unless
the repository workflow or user asks for those actions. If the planner reports
an ambiguity, stop and ask for the classification instead of editing around
it.
