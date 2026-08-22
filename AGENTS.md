# Projector contributor instructions

Projector is a public, portable framework. Keep repository behavior independent
of personal account names, home-directory layouts, machine-local tools, and one
host's private configuration.

## Preserve the project model

Read `docs/projects/README.md` before changing project plans.

- Store each project at `docs/projects/<name>/readme.md`. The lowercase
  filename is the project sentinel.
- Derive the canonical name from the path relative to `docs/projects/`.
- Use only `now`, `next`, `later`, or `done` in `status`
  frontmatter.
- Treat `now` as the only executable-readiness claim. A plan at `now` must
  answer or deliberately defer every question that blocks implementation.
- Change status in frontmatter. Never move a project, create a shared status
  list, or generate a tracked index.
- Allow supplemental files and recursively nested projects. A directory is a
  project only when it has its own lowercase `readme.md`.
- Number plan sections and append new sections without renumbering cited
  sections.
- Keep status current in the same pull request that changes what it claims.
  Mark a completed project `done` and record whether it shipped, was
  abandoned, or was superseded.

Use `projector` for project discovery and mutation rather than duplicating
frontmatter parsing in a skill:

```sh
projector list --json
projector show <name> --json
projector status <name> <status>
projector check
```

## Keep the core portable

The Python CLI has no runtime dependencies and supports Python 3.9 or newer.
Prefer the standard library unless a dependency has a concrete cross-platform
benefit that justifies its installation and release cost.

The root `skills/` directory is the single source for both hosts.
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` package that
same tree. Do not copy or generate host-specific skill forks. Put a genuinely
host-specific enhancement in host packaging and keep the shared workflow
usable without it.

MCP is optional. Do not make the CLI or a core skill depend on an MCP server.
Add a server only when structured remote tools, authentication, or persistent
infrastructure creates value beyond the local CLI.

Skills must obtain repository policy and GitHub identities from explicit user
input, repository instructions, or user configuration. Never add a personal
default to a public skill. Preserve authorization boundaries: visibility into
a repository, branch, review, or account does not authorize mutation.

## Write current documentation

`docs/` describes behavior that exists on the current branch. Update it with
behavior changes. Write new and substantially revised documentation in the
Google developer documentation style: second person, present tense, active
voice, sentence-case headings, exact identifiers in code font, and a command or
example when it communicates more directly than prose.

Markdown files use the wrapping already established around them. GitHub pull
request bodies and review comments use unwrapped prose paragraphs because
GitHub renders hard line breaks.

## Run the validation gate

Run the full gate from the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -v
PYTHONPATH=src python3 -m projector check
claude plugin validate .
claude plugin validate skills
git diff --check
```

Also run the Codex plugin validator and the skill validator when you change a
manifest or skill. Those validators require PyYAML; install it in a temporary
environment rather than adding it as a Projector runtime dependency.

Test mutation behavior in temporary Git repositories. Include exact casing,
nested projects, dirty-file preservation, ambiguous input, and binary
NUL-containing reference fixtures where relevant.

## Hand work over for review

Open pull requests; never merge them. The user owns the merge checkpoint.
Create dependent work as a real GitHub stack when it crosses a reviewability
boundary, and keep tests and documentation with the code they verify.

Use an imperative pull request title and a body that explains why the change
exists. End every body with a `## Testing` section containing commands you ran
from the directory you name, the expected result, the failure signal, and any
state the commands leave behind. Do not put stack scaffolding in the body
because squash merges preserve that body as the commit message.

For review findings, verify first, commit locally, reply with the commit, push,
resolve the thread, and re-fetch it in that order. Fix stacked code on the
branch that introduced it and rebase every layer above it.
