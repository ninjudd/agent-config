# Projector

Projector is a Git-native framework for getting work done in any repository.
It gives every project a permanent plan under `docs/projects/`, derives status
views from frontmatter, and supplies one CLI for people and coding agents.

Projects never move when their status changes. Two branches working on
different projects therefore edit different files instead of contending on a
shared `now.md`, `next.md`, or `later.md` queue.

## Install the CLI

Projector requires Python 3.9 or newer. Install an isolated executable with
`pipx`:

```sh
pipx install git+https://github.com/ninjudd/projector.git
projector --help
```

For local development, install the checkout in editable mode:

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/projector --help
```

## Adopt Projector in a repository

Run `init` from anywhere inside a Git repository:

```sh
projector init
projector create cool-new-feature --status next --no-edit
projector check
```

This creates the convention at `docs/projects/README.md` and the project plan
at `docs/projects/cool-new-feature/readme.md`. A project can contain supporting
documents and nested projects:

```text
docs/projects/cool-new-feature/
├── readme.md
├── design.md
└── sub-feature/
    └── readme.md
```

Each project entry point has one `status` value: `now`, `next`, `later`, or
`done`. Run `projector list` to group projects at query time. Projector never
writes a tracked status index.

## Use the CLI

```sh
projector list [--status now|next|later|done] [--json]
projector show <project> [--json]
projector search <query> [--status <status>] [--json]
projector create <project> [--status later] [--parent <project>]
projector edit <project>
projector status <project> <status>
projector done <project>
projector check [--json]
```

Use `--json` when an agent or script consumes output. Every JSON response has
`"schema_version": 1`; diagnostics go to stderr. See [the CLI
reference](docs/cli.md) and [the project convention](docs/projects/README.md)
for the complete contracts.

## Develop Projector

Run the validation gate from the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -v
PYTHONPATH=src python3 -m projector check
git diff --check
```
