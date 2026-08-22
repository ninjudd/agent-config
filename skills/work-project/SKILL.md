---
name: work-project
description: Implement a Projector project while keeping its plan and status current. Use when the user asks to start, continue, or complete work recorded under docs/projects.
---

# Work Project

Use the project plan as the durable statement of intent while treating the
repository and current runtime behavior as authoritative evidence.

## Start from the project

1. Read the repository instructions and run `projector show <name> --json`.
2. Read the entry point, its supplemental files, relevant nested projects, and
   the code and documentation they cite.
3. Check every open question before claiming readiness. Resolve a product
   choice with the user when the repository cannot answer it.
4. Run `projector status <name> now` only when implementation truly begins.
   Keep the status change in the implementation pull request; do not open a
   status-only change.

## Implement coherent work

Build the requested outcome, not merely the easiest plan item. Keep changes
reviewable and verify each behavior in proportion to its risk. Follow the
repository's branch, stack, commit, review, and merge rules.

Update the project plan in the same change whenever implementation settles a
decision, changes scope, reveals a new constraint, or completes an acceptance
criterion. Append numbered sections rather than renumbering cited sections.
Create a nested project only when it has an independently useful lifecycle;
use a supplemental document for details belonging to the parent.

Do not infer a parent's status from a child or vice versa. Do not move project
directories, generate a tracked status index, or duplicate status elsewhere.

## Verify the current slice

Run the repository's full validation gate plus:

```sh
projector show <name>
projector check
git diff --check
```

Compare the result against the plan's acceptance criteria. If required work
remains, record the exact state and leave the project `now`, `next`, or
`later` as the user's real scheduling intent requires. If every criterion is
proven, continue with `finish-project` in the same implementation change.
