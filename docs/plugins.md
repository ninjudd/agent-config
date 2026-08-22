# Install Projector skills

Projector keeps one canonical skill tree under `skills/`. The Claude Code
manifest at `.claude-plugin/plugin.json` and the Codex manifest at
`.codex-plugin/plugin.json` both point to that directory. A host loads the same
instructions and supporting scripts without a generated copy or host-specific
fork.

## Install for Claude Code

Add the Projector marketplace and install its plugin at user scope:

```sh
claude plugin marketplace add ninjudd/projector --scope user
claude plugin install projector@projector --scope user
```

Invoke a skill with the plugin namespace, for example:

```text
/projector:plan-project plan a safer deploy workflow
```

Validate a checkout before publishing it:

```sh
claude plugin validate .
claude plugin validate skills
```

## Install for Codex

Add the same repository as a Codex marketplace and install the plugin:

```sh
codex plugin marketplace add ninjudd/projector
codex plugin add projector@projector
```

Invoke a skill directly, for example:

```text
$plan-project plan a safer deploy workflow
```

The Codex manifest exposes the same `skills/` path as Claude Code. It adds only
install-surface metadata; it does not wrap or rewrite skill instructions.

## Install from a checkout

Run the installer to add the local checkout as both marketplaces and install
the CLI with `pipx`:

```sh
./install.sh all
```

Select one component with `cli`, `claude`, or `codex`. The host-only commands
do not install the CLI, so install it separately before running a project
workflow. `all` installs each host CLI it finds, skips a missing host, and exits
69 only when neither Claude Code nor Codex is installed.

## Upgrade from agent-config

The old installer linked whole configuration and skill directories into each
host. Projector installs a named plugin instead. During an upgrade,
`install.sh` removes a legacy link only when its target exactly matches this
checkout's old source path. It leaves regular files, other symlinks, settings,
credentials, personal instructions, and unrelated plugins untouched.

Inspect the upgrade before applying it:

```sh
./install.sh status
./install.sh claude
./install.sh codex
```

The host plugin managers own installed copies and future updates after the
migration.

## Work without MCP

Projector currently ships no MCP server. Every core skill uses the public
`projector` CLI and ordinary Git or GitHub commands. A future MCP adapter can
expose the same versioned project operations without becoming the package that
contains the skills.
