---
name: start-fix-loop
description: Watch chat-owned GitHub pull requests for review findings, verify and fix each one, then reply, push, and resolve it. Use when the user asks to keep fixing review feedback as it arrives or drive PRs to a clean review.
---

# Start Fix Loop

Run a persistent background loop alongside foreground work. Watch only pull
requests this conversation created or explicitly adopted, and keep watching
until the user stops the loop.

Watch only the repository containing the current working directory. Covering a
second repository requires starting this skill from that repository with its
own tracked set and watcher state.

## Resolve ownership

The **operator** owns the pull request branches and is the identity allowed to
push fixes. Resolve that login once from explicit user input, repository
instructions, or host user configuration, in that order. Confirm it with
`gh auth status` and `gh api user --jq .login` under the token used for
pushes.

A review loop may place a different reviewer's token in `GH_TOKEN`. If the
ambient identity is not the operator, do not derive scope from it and do not
push through it. Hold the validated operator login literally; never use
`@me`.

Default scope is not every operator pull request. Build the tracked set from
pull requests created by this conversation plus any pull request the user
explicitly assigns. A newly opened pull request joins only when this
conversation created or adopted it. Never modify a teammate's branch merely
because the watcher can see its findings.

## Establish the loop

1. Read repository instructions, `AGENTS.md` or `CLAUDE.md`, and applicable
   GitHub skills.
2. Resolve the repository, checked-out branch, exact tracked pull request set,
   each base and head SHA, author, state, review decision, and unresolved review
   threads. Include every layer of a stack created by this conversation.
   Baseline only already-resolved threads. Never baseline an unresolved thread;
   every finding already waiting when the loop starts remains outstanding.
3. Verify the operator can push each tracked branch. Do not test with an empty
   commit or direct push.
4. Record the tracked `owner/repo#number` set in a persistent recurring goal.
5. Run the bundled `scripts/watch-threads.sh` with a durable state file, the
   repository, an interval of at least 30 seconds, and a finite renotification
   interval. Use the host's persistent process or monitor facility.
6. Filter every emitted event against the literal tracked set. The watcher
   scans repository-wide review state so it can remain generic; visibility is
   not authorization.

Before adopting an existing watcher, fetch unresolved threads, verdicts, and
body-only reviews directly. Verify the watcher's state file contains every
expected unresolved row. Restart the watcher when its script changed after it
started; a live process cannot prove which file version it loaded.

The watcher is level-triggered:

- `FINDING` reports an unresolved inline thread.
- `VERDICT` reports `CHANGES_REQUESTED`, including a review whose findings
  exist only in its body.
- `REVIEW` reports a non-verdict review body that has no inline thread.

Read review bodies and compare them with the thread set. Dispose of a body-only
finding in a pull-request-level comment because there is no thread to reply to
or resolve.

## Verify and fix findings

Handle findings in posting order, batching only related findings that touch the
same code:

1. Verify the claim against the exact pushed head and surrounding code. Decline
   a false finding with evidence rather than changing correct behavior.
2. Reproduce a valid defect with a failing test, error, or measurement.
3. Implement the narrow fix in the branch that owns the code. Read the lines
   around an insertion anchor before editing so an attribute, decorator, or
   comment is not silently detached.
4. Prove a regression test fails without the fix and passes with it.
5. Run the repository's full test, lint, format, documentation, and validation
   gate.
6. Keep independent fixes in independent commits; batch findings that share one
   cause.

If the correct behavior requires a user decision, ask instead of guessing and
keep watching unrelated findings. If a finding recurs after a pushed fix, stop
and report the recurrence before changing it again.

## Commit, reply, push, resolve

For every accepted finding, preserve this order:

1. Commit the validated fix locally.
2. Reply in its review thread under the operator identity. Name the commit and
   state what was reproduced and changed.
3. Push the pull request branch, never its base branch.
4. Resolve the thread only after the push succeeds.
5. Re-fetch `reviewThreads` and confirm `isResolved: true`.

Reply before pushing so a reviewer triggered by the push sees the reasoning,
but push promptly because the named commit is briefly local-only. If a push
fails, post that fact, leave the thread unresolved, and report the blocker.

Never resolve a finding you declined or could not fix. An open declined thread
is the user's merge decision. Re-read and rerun the pull request body's
`Testing` commands after each fix batch, and update stale claims in unwrapped
GitHub prose.

## Preserve stacked ownership

Fix code on the stack branch that introduced it. When a lower layer changes,
use the installed stack workflow to cascade-rebase and push every layer above
it, then rerun each affected layer's full gate. Do not patch parent code inside
a child merely to avoid rebasing.

After a parent merges, verify the child points at the intended base and remains
mergeable. Use the stack workflow's sync operation when available. Never merge
any layer; merging remains the user's checkpoint.

## Report clean state and continue

A pull request is clean only when:

- a clean verdict names its current head,
- no unresolved threads remain,
- `reviewDecision` is not `CHANGES_REQUESTED`, and
- the current head is the one actually reviewed.

Report that state with the head SHA, fix commits, declined findings, and
validation results, then keep watching. A stale `CHANGES_REQUESTED` after all
fixes is a wait for re-review, not another code change. Do not manufacture an
empty commit to trigger it.

Drop closed or merged pull requests from the tracked set. An empty set is idle,
not an instruction to stop; remain ready for pull requests this conversation
creates or adopts later. Stop the loop only when the user asks, a required user
decision blocks one finding, validation cannot be restored, or every remaining
finding on a pull request is deliberately declined.

## Never

- Never merge.
- Never push through the reviewer identity or to an unowned branch.
- Never discard or overwrite uncommitted work to switch branches.
- Never claim a watcher, review, or clean state without checking live evidence.
- Never invoke an external reviewer unless the user explicitly names it.
