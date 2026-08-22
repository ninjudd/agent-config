---
status: next
---

# Turn agent-config into Projector

## 1. Outcome

Projector is a framework for getting work done in any Git repository. It keeps
project intent in Git, gives people and agents one command-line interface for
working with that intent, and supplies durable review and fix loops for taking
code through pull request feedback.

The finished repository has three primary parts:

- A convention for project plans under `docs/projects/`.
- A `projector` CLI for finding, viewing, creating, editing, validating, and
  completing projects.
- Portable Agent Skills for planning and executing projects and for running
  code review and fix loops, distributed through both Claude Code and Codex
  plugins.

The repository is no longer the public home for one person's global agent
configuration. Personal and machine-specific material belongs in
`ninjudd/agent-config-private`.

## 2. Product principles

Projector follows these principles:

- **Git is the database.** A clone contains the project plans and their history.
  Projector does not require a service, account, daemon, or generated index.
- **One project has one permanent home.** A status change edits frontmatter; it
  does not move a file or maintain a second representation.
- **Concurrent projects change different files.** Listing and prioritization
  are queries, so branches do not contend on `now.md`, `next.md`, or
  `later.md`.
- **Projects can grow recursively.** Every feature starts as a directory and can
  acquire supporting documents or nested projects without changing shape.
- **The command line serves people and agents.** Human output is concise, while
  stable JSON supports automation.
- **Skills express workflows; the CLI supplies mechanics.** Skills tell an
  agent how to plan, execute, review, and finish work. They call the same
  commands a person can inspect and run.
- **Claude Code and Codex are equal targets.** Projector authors each portable
  skill once and keeps host-specific packaging or enhancements outside the
  shared workflow.
- **Repository policy stays local.** Projector provides useful defaults without
  embedding one user's GitHub accounts, home-directory layout, or review rules.

## 3. Project format

Every project lives directly or recursively under `docs/projects/` and has a
lowercase `readme.md` entry point. The path relative to `docs/projects/` is its
canonical name:

```text
docs/projects/payments/readme.md
docs/projects/payments/invoices/readme.md
```

The first path names `payments`; the second names the nested project
`payments/invoices`. Supplemental directories do not become projects unless
they contain their own lowercase `readme.md`.

`readme.md` uses YAML frontmatter with one required status:

```yaml
---
status: next
---
```

The allowed values are `now`, `next`, `later`, and `done`. They replace both
the shared queue files and proposed queue directories. A completed project's
plan records whether it shipped, was abandoned, or was superseded. Projector
can add a separate resolution field later if real queries require one.

This vocabulary also supersedes the older lifecycle keywords. `now` replaces
the readiness claim made by `Active` and `Blocked`; `next` and `later` make no
readiness claim; and `done` records the outcomes previously represented by
`Shipped`, `Superseded`, and `Abandoned`. Section 8 defines the complete
migration, including `Draft`, `Stalled`, and `Reference`.

Use lowercase `readme.md` so GitHub renders the project plan when you browse its
directory while the filename remains subtly distinct from a conventional
uppercase `README.md`. The exact casing is part of the format. Projector checks
both directory entries and tracked Git paths rather than trusting
case-insensitive path lookup when it validates the name.

This choice intentionally supersedes the existing `AGENTS.md` rule that names
uppercase `README.md` as a project folder's entry point. The transformation in
section 7 rewrites that rule and the status vocabulary together so installed
instructions and Projector's public convention cannot disagree.

Number the sections in a plan and never renumber them. Because status changes
do not move the directory, a citation such as
`docs/projects/payments/readme.md § 6` stays valid throughout the project
lifecycle. Only an intentional rename or reparenting requires a reference
sweep.

The convention in `docs/projects/README.md` is the first working version of
this format. This plan dogfoods it at `docs/projects/projector/readme.md`.

## 4. Command-line interface

The `projector` CLI discovers the Git root from the current directory and uses
that repository's `docs/projects/` tree. It offers explicit `--root` and
`--projects-dir` overrides for unusual layouts. It never needs network access
for project operations.

The initial command set is:

```sh
projector init
projector list [--status now|next|later|done] [--json]
projector show <project> [--json]
projector search <query> [--status <status>] [--json]
projector create <project> [--status later] [--parent <project>]
projector edit <project>
projector status <project> <status>
projector done <project>
projector check [--json]
```

The commands behave as follows:

- `init` creates `docs/projects/README.md` when a repository has not adopted
  the convention. It does not overwrite an existing project system.
- `list` recursively discovers `readme.md` files and returns their canonical
  names, titles, statuses, and owners when present. Its default human view
  groups results by status without writing those groups to disk.
- `show` resolves a canonical name and prints the frontmatter and rendered or
  plain plan content.
- `search` searches project names, metadata, plans, and supplemental Markdown
  files while reporting the containing project.
- `create` validates the name, creates one project directory and `readme.md`,
  and opens the new plan in `$EDITOR` when the command is interactive. Creating
  `payments/invoices` makes a nested project without changing the parent plan.
- `edit` resolves and opens `readme.md` without requiring the caller to know its
  path.
- `status` changes only the target project's frontmatter. `done` is a readable
  shorthand that also prompts the user to record the outcome in the plan.
- `check` rejects missing or invalid frontmatter, project directories without a
  usable plan, incorrect `readme.md` casing, duplicate or ambiguous discovery
  results, malformed Markdown links between project files, and invalid nesting.

Mutation commands show the exact files they changed. They make the narrowest
textual edit and preserve all unrelated frontmatter, formatting, and
uncommitted content. They fail if the target changed after the command read it
or if the update would require rewriting unrelated content. They make no
commits. Non-interactive use requires all choices as flags and never opens an
editor.

JSON output has a versioned shape, uses stdout only for data, and sends
diagnostics to stderr. Exit codes distinguish invalid project data, a missing
project, ambiguous input, and command misuse so skills do not parse prose.

## 5. Conflict behavior

The format removes the common conflict points by construction. Creating or
updating unrelated projects changes unrelated `readme.md` files. Listing and
searching do not update an index. Changing `later` to `now` edits one scalar in
the affected project instead of moving a tree or editing a shared list.

Two branches that change the same project can still conflict. That conflict is
useful: both branches are making claims about the same work and should be
reconciled. Projector must not avoid it by creating duplicate status records.

A parent and child can have independent statuses. For example, a parent can
remain `now` after one nested project becomes `done`. The CLI displays the
hierarchy and can roll up child counts, but it never infers or rewrites a
parent's status from its children.

## 6. Portable skills and plugins

Projector treats its CLI, project format, templates, and Agent Skills as the
portable core. Claude Code and Codex each receive a thin plugin package around
that core. Neither host's manifest or extension system becomes the source of
truth for a workflow.

Both products use a plugin as the packaging layer for related skills and an
optional MCP server. OpenAI documents a plugin as one or more skills, an MCP
server, or both in its
[plugin architecture](https://developers.openai.com/plugins/concepts/plugins).
Claude Code likewise packages skills and optional MCP servers, along with
host-specific features such as hooks and monitors, in its
[plugin format](https://code.claude.com/docs/en/plugins).

The source has this conceptual shape:

```text
Projector
├── shared Agent Skills
├── shared CLI, schemas, and templates
├── Claude Code plugin packaging
├── Codex plugin packaging
└── optional shared MCP server
```

Write every shared `SKILL.md` against the Agent Skills features supported by
both hosts. Put host-specific frontmatter, hooks, monitors, agents, or other
enhancements in its packaging layer, and do not make a core workflow depend on
them. Test the same source skill in both Claude Code and Codex before release.

Install `projector` as an ordinary executable available on `PATH`. A host
plugin may help install or locate it, but a shared skill must not rely on
Claude-specific executable injection or a Codex-specific runtime. The CLI
remains independently useful to a person and to any shell-capable agent.

An MCP server is an optional capability adapter, not the package that contains
the skills. Add one when a host needs structured tools without shell access,
authentication to a remote service, shared infrastructure, or persistent
server-side behavior. A local server can call the same project library as the
CLI, while a remote server can implement the same contract against a hosted
repository.

Design the versioned CLI JSON so these mappings remain mechanical:

```text
projector list --json    -> project_list
projector show --json    -> project_get
projector create --json  -> project_create
projector status --json  -> project_set_status
projector check --json   -> project_validate
```

Do not require MCP for the first release. Claude Code and Codex must both be
able to complete the core project workflows with the shared skills and local
CLI alone.

The existing review and fix loops remain core Projector capabilities, but they
must become portable. Their current instructions assume the `ninjudd` author
and `minjudd` reviewer identities and personal repository policy. Projector
will obtain identities and policy from repository instructions, explicit skill
arguments, or user configuration. It will fail clearly when GitHub cannot
supply a separate reviewer instead of silently weakening a verdict.

Projector adds three project workflow skills:

- `plan-project` inspects the repository, creates or refines a project plan,
  records decisions and open questions, and assigns `later`, `next`, or `now`
  from the user's intent. It does not claim readiness merely because a plan
  exists.
- `work-project` resolves a project through the CLI, reads its full context,
  makes it `now` when work truly begins, implements a coherent slice, and keeps
  the plan current in the same pull request.
- `finish-project` verifies acceptance criteria, records the outcome, changes
  the project to `done` in the implementation pull request that completes it,
  and confirms that no follow-up closeout pull request is being deferred.

All three use `projector check` before handing work over. They share project
mechanics through the CLI rather than duplicating frontmatter parsing in skill
instructions.

`start-review-loop` continues to review exact pull request heads and publish
verified findings. `start-fix-loop` continues to verify findings before fixing,
replying, and resolving them. `gh-stack` remains a supporting GitHub workflow
skill rather than a primary Projector component.

## 7. Repository transformation

The current repository contains a global `AGENTS.md`, a symlink-oriented
`install.sh`, placeholder Claude and Codex directories, the two loop skills,
`gh-stack`, and the vendored `gog` skill. The transformation separates reusable
workflow from personal configuration:

1. Replace the agent-config README with the Projector product overview and
   document installation, adoption, and the project format.
2. Replace the global-config installer with distribution for the `projector`
   CLI and separate Claude Code and Codex plugin packages around the shared
   skills. Installing Projector must not replace a user's complete Claude or
   Codex configuration directories.
3. Rewrite the public `AGENTS.md` project convention to use lowercase
   `readme.md` and the four new statuses. Keep that reusable convention in
   Projector, reduce the rest of the file to contributor guidance, and move
   only personal global instructions and machine-local configuration to
   `ninjudd/agent-config-private`.
4. Copy `skills/gog/` to `ninjudd/agent-config-private`, verify the private
   install sees it, and then remove it from Projector. The copy and removal must
   not create a window where the skill is lost.
5. Generalize the review and fix skills without weakening their exact-head,
   separate-reviewer, verified-finding, or never-merge safeguards.
6. Add the project workflow skills after the CLI contract they depend on is
   covered by tests, then exercise the same skill source in Claude Code and
   Codex.
7. Remove agent-config placeholders and compatibility behavior after the new
   install path covers every reusable component that remains.

The remote already points at `ninjudd/projector`; the repository contents and
release surface now need to catch up with that identity.

## 8. Migrate existing repositories

Modal, Fyra, Field, and msg use the older `now.md`, `next.md`, `later.md`, and
`all/` convention. Projector needs a migration workflow that preserves history
and citations as far as Git allows.

For each old project, migration performs these steps:

1. Read list membership and status frontmatter before changing any paths.
2. Convert `all/name.md` or `all/name/README.md` to `name/readme.md` with
   `git mv`.
3. Map `Shipped`, `Superseded`, and `Abandoned` to `status: done`, regardless
   of list membership, and retain the precise outcome in the body. Move a
   `Reference` document to ordinary `docs/`, because it has no project
   lifecycle.
4. For the remaining projects, map list membership to `now`, `next`, or
   `later`. When no list contains one, map `Active` and `Blocked` to `now`, and
   map `Draft` and `Stalled` to `later`. Preserve a blocker explanation in the
   body even when its scheduling status is `next` or `later`.
5. Use list membership for a project with no lifecycle keyword. Stop for manual
   classification when a project has neither a recognized keyword nor list
   membership; do not guess.
6. Preserve supplemental files and existing nested project structure.
7. Rewrite inbound path references in documentation and code comments.
8. Remove the old list files and `all/` only after every project is accounted
   for.
9. Run `projector check`, then compare an `rg` reference sweep with
   `command grep -rl` before declaring the migration complete.

The first release implements this migration as a temporary `migrate-projects`
skill built on the public CLI and Git commands, not as a permanent
`projector migrate` command. Its dry run reports every proposed mapping and
refuses ambiguous input rather than guessing. Promote migration into the CLI
only if ongoing use proves it is a durable operation.

## 9. Implementation sequence

Build Projector in this order:

1. Specify fixtures for top-level projects, nested projects, supplemental
   directories, malformed frontmatter, and all four statuses. Implement
   discovery, parsing, `list`, `show`, `search`, and `check` against them.
2. Implement `init`, `create`, `edit`, `status`, and `done`, including
   non-interactive behavior and stable JSON.
3. Implement and test migration from the current convention on representative
   repository fixtures.
4. Add the three project workflow skills and generalize the review and fix
   loops against the CLI and repository-local configuration. Validate the
   shared skills through both host plugin packages.
5. Rework installation and documentation, move private content out, and test
   clean Claude Code and Codex installs plus an upgrade from agent-config.
6. Adopt Projector in one existing repository, use the result to correct the
   migration, and then migrate the remaining repositories.

These steps sequence dependencies; they do not prescribe pull request size.
Combine adjacent work when it makes one reviewable argument, and split only
when a part has independent value or exceeds the reviewability ceiling.

## 10. Acceptance criteria

Projector is ready for its first release when all of these are true:

- A new Git repository can adopt the convention without copying personal
  configuration.
- Two branches can create different projects and change their statuses without
  touching a shared index or moving either project.
- The CLI discovers top-level and nested projects from any subdirectory in the
  repository.
- Human output supports quick browsing, and documented JSON output supports
  agent automation without prose parsing.
- Mutation commands preserve unrelated content, refuse destructive ambiguity,
  and leave changes visible for normal Git review.
- `projector check` catches invalid statuses, malformed plans, wrong entry-point
  casing, ambiguous nesting, and broken project links.
- The project skills can plan, start, update, and finish a real project using
  only the public CLI contract.
- Claude Code and Codex load the same source skills through their own plugin
  packages and produce equivalent project changes from the same fixtures.
- Neither host requires an MCP server to complete the core workflows.
- The review and fix loops work without hard-coded personal identities and
  retain their existing safety guarantees.
- `gog` and other personal configuration are installed from
  `ninjudd/agent-config-private`, not Projector.
- The documented migration succeeds on a fixture representing the current
  Modal, Fyra, Field, and msg layout.

## 11. Decisions

- **Store status in frontmatter.** This avoids shared queue files and path
  churn.
  Queue directories and symlinks were rejected because both create a second
  representation of state, and moving between queue directories breaks links.
- **Put projects directly under `docs/projects/`.** An `all/` segment provides
  no information once the CLI generates every view.
- **Make every project a directory.** This supports supplemental files and
  nested projects from the beginning without later file-to-directory moves.
- **Use lowercase `readme.md` as the project sentinel.** GitHub renders it
  automatically, while the casing distinguishes a project plan from a standard
  `README.md`. Projector enforces the distinction from Git's recorded path.
- **Derive identity from the permanent relative path.** Frontmatter does not
  repeat a name that can drift. Renaming or reparenting is an intentional
  identity change with a reference sweep.
- **Keep one source of truth.** The CLI does not generate tracked indexes,
  status links, or cache files.
- **Share skill source across Claude Code and Codex.** Host plugins are
  distribution adapters, not forks of the workflows.
- **Keep MCP optional.** It can expose the same project operations locally or
  remotely when a server adds value, but it does not contain the skills and is
  not required for local Git work.
- **Keep optional metadata in prose first.** Completion outcomes, tags, and
  dependencies become structured fields only after a real query needs them.
- **Keep policy at the repository boundary.** Shared skills read project rules
  and identities from repository instructions or explicit user input. Personal
  defaults remain in host configuration and never become Projector policy.
- **Migrate through a temporary skill first.** The initial migration uses
  public CLI primitives and Git; it becomes a permanent CLI command only if the
  workflow remains useful after the known repositories move.
- **Separate reusable workflow from private configuration.** Projector remains
  portable, while `agent-config-private` can keep personal tools and policy.

## 12. Open questions

- Which implementation language and packaging route provide the simplest
  cross-platform installation while preserving a single dependable CLI?
- What repository layout lets both host manifests package the same skill files
  without copying them into generated trees?
