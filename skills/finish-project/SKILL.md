---
name: finish-project
description: Verify a Projector project's acceptance criteria, record its outcome, and mark it done in the completing change. Use when implementation appears complete or the user ends a project as shipped, abandoned, or superseded.
---

# Finish Project

Close the project only when its durable plan and the repository agree about
the outcome.

## Prove the outcome

1. Read the repository instructions and `projector show <name> --json`.
2. Enumerate every acceptance criterion and identify the strongest available
   evidence for it: tests, runtime behavior, generated artifacts, or current
   external state.
3. Run the repository's complete validation gate. Treat missing or indirect
   evidence as incomplete rather than assuming intent proves delivery.
4. Inspect nested projects. Their independent statuses do not automatically
   block the parent, but unresolved work that belongs to the parent's promised
   outcome does.

## Record completion

Update the plan with the actual outcome and any important deviation from the
design. State whether the project shipped, was abandoned, or was superseded,
and link the replacement when one exists. Preserve the history of decisions
and unanswered questions that still explain the result.

Run `projector done <name>` in the implementation change that completes the
project. Do not defer the status update to a follow-up pull request, and do not
mark an early slice done when later slices still carry the same promised
outcome.

## Validate the handoff

Run:

```sh
projector show <name>
projector check
git diff --check
```

Confirm that the plan names the outcome, every acceptance criterion has
evidence or an explicit non-delivery disposition, and no separate closeout
change remains. Follow the repository's handoff rules and never merge unless
the user explicitly owns that action.
