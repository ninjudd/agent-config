# Project plans

Store each project in a permanent directory under `docs/projects/`. Use a
lowercase `readme.md` entry point with `status: now|next|later|done` YAML
frontmatter. Nest a project directory inside another project when the work is
a subproject. Keep supplemental files beside the entry point that owns them.

Project status changes edit frontmatter. Do not create shared status lists,
status directories, or symlinks, and do not move a project when its status
changes. Number plan sections and never renumber them after another document
or code comment cites them.

Run `projector list` to browse projects and `projector check` to validate the
tree.

