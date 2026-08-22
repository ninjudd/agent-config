# Use the Projector CLI

Projector discovers the Git root from your current directory and reads projects
under `docs/projects/`. Pass `--root <path>` to select a repository explicitly,
or `--projects-dir <path>` to use another project-plan directory.

## Adopt a repository

Run `init` once to create `docs/projects/README.md`:

```sh
projector init
```

If projects already exist but the convention file is missing, `init` adds only
that file. It refuses to replace an existing convention file.

## Browse projects

Run `list` to group projects by status without creating an index:

```console
$ projector list
now:
  projector                    Turn agent-config into Projector
```

Add `--status next` to select one status. Run `show <project>` to print the
entry point, including its frontmatter, or `search <query>` to search project
names, metadata, plans, and supplemental Markdown files.

Project names are paths relative to `docs/projects/`. For example,
`docs/projects/payments/invoices/readme.md` is `payments/invoices`.

## Create and update projects

Create a top-level or nested project:

```sh
projector create payments --status next
projector create invoices --parent payments --status later
```

`create` opens the new plan when stdin and stdout are interactive. Pass
`--no-edit` to leave the generated plan ready for another command. In a
non-interactive session, Projector never opens an editor.

Run `edit <project>` to open an existing plan with `$VISUAL` or `$EDITOR`.
`edit` has no `--json` mode because the editor owns the interactive session.
It exits 69 without a terminal or configured editor.

Change only the status scalar with `status`, or use `done` as a readable
shorthand:

```sh
projector status payments now
projector done payments/invoices
```

Projector preserves unrelated frontmatter, formatting, and uncommitted plan
content. It writes through a temporary file in the project directory and
refuses the update if the file changes after Projector reads it. Mutation
commands make no Git commits.

## Validate projects

Run `check` before handing over project changes:

```console
$ projector check
Project plans are valid.
```

The command reports malformed frontmatter, invalid statuses, missing top-level
plans, uppercase project entry points, case collisions, symlinks, malformed
Markdown links, and missing local link targets. It reads both directory entries
and Git's tracked paths so casing errors remain visible on case-insensitive
filesystems.

## Consume JSON

Pass `--json` to `init`, `list`, `show`, `search`, `create`, `status`, `done`,
or `check`. Responses use stdout only for JSON and include
`"schema_version": 1`.

For example:

```console
$ projector list --status now --json
{
  "projects": [
    {
      "name": "projector",
      "owner": null,
      "path": "docs/projects/projector/readme.md",
      "status": "now",
      "title": "Turn agent-config into Projector"
    }
  ],
  "schema_version": 1
}
```

Projector uses these exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | The command completed successfully. |
| `2` | Command syntax or an argument is invalid. |
| `65` | Project data is invalid or a mutation is unsafe. |
| `66` | The requested project does not exist. |
| `67` | The requested project is ambiguous. |
| `69` | Git or the interactive editor environment is unavailable. |
