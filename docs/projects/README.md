# Projects

Use `docs/projects/` to keep project plans with the code they change. Each
project has one permanent directory, and the project status lives in
frontmatter. You do not maintain separate queue files or move a project when
its status changes.

## Lay out projects

Put each top-level project directly under `docs/projects/`. Name its entry point
`readme.md`:

```text
docs/projects/
├── README.md
└── cool-new-feature/
    ├── readme.md
    ├── design.md
    └── sub-feature/
        └── readme.md
```

A directory is a project when its `readme.md` begins with Projector status
frontmatter. GitHub renders that file when you browse the directory, while the
frontmatter lets tools distinguish a nested project from a directory that only
organizes supplemental files. Add `design.md`, `decisions.md`, implementation
notes, or other files when the work needs them; none are required.

Use the exact lowercase name. Uppercase `README.md` remains the conventional
entry point for the documentation root and non-project directories; lowercase
`readme.md` identifies a Projector project. `projector check` enforces this
distinction, including on case-insensitive filesystems.

The path relative to `docs/projects/` is the project's name. In the example,
the two project names are `cool-new-feature` and
`cool-new-feature/sub-feature`. A nested project belongs to its parent but has
its own status and plan.

Do not add an `all/` directory. Do not create `now/`, `next/`, `later/`, or
`done/` indexes, directories, or symlinks. Those structures make status changes
modify shared files or paths. Recursive `readme.md` discovery provides the
index instead.

## Set project status

Begin every `readme.md` with YAML frontmatter containing one `status` field:

```yaml
---
status: later
---
```

Use one of these values:

- `now`: The project is receiving attention. Keep a blocked project here when
  it still occupies the team's current attention, and explain the blocker in
  the project plan.
- `next`: The project is ready to become current when capacity opens.
- `later`: The project is recorded but not scheduled.
- `done`: The project no longer needs work. State whether it shipped, was
  abandoned, or was superseded in the project plan.

Add `owner` only in a repository where more than one person could own the
project. Add other metadata only after a command or workflow needs it. The file
path already supplies the project name, so do not duplicate it in frontmatter.

Change status in the pull request that makes the change true. For example, the
pull request that begins implementation changes the status from `next` to
`now`. The pull request that completes the final implementation changes it to
`done`. A stale status is worse than a missing status.

## Write a project plan

Use numbered sections so code and later documents can cite a stable decision,
for example `docs/projects/cool-new-feature/readme.md § 4`. Do not renumber
existing sections. Add new sections at the end.

Write the smallest plan that makes the intended outcome, constraints,
decisions, verification, and unresolved questions clear. Keep the reason for a
status change in the body rather than adding more status values. Split material
into a supplemental file when it obscures the main plan.

## Find projects before the CLI exists

Projector will provide commands for listing, searching, editing, and validating
projects. Until that CLI ships, use repository-local searches:

```sh
find docs/projects -name readme.md -print
rg -l '^status: now$' docs/projects -g readme.md
rg -n 'search term' docs/projects
```

These commands generate a view from the project files. They do not write an
index that can become stale or conflict with another branch.

## Rename a project deliberately

Changing status never changes a project path. If the project itself needs a
new name or parent, use `git mv` and update every inbound reference in the same
change. Start the sweep with `rg`, then confirm it with `command grep -rl` so a
binary-classified text file cannot hide a stale reference.
