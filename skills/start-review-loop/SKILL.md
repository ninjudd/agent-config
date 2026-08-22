---
name: start-review-loop
description: Monitor an operator's open pull requests in the current GitHub repository, review each exact pushed SHA locally, and publish verified findings from a separate reviewer identity. Use when the user asks to keep reviewing current and subsequent PR heads.
---

# Start Review Loop

Run a persistent exact-head review loop for the current repository. A review
starts only when an unreviewed pushed SHA exists and local inspection of that
SHA actually begins.

## Resolve identities and scope

Two GitHub identities are required:

- The **operator** authors the pull requests in scope.
- The **reviewer** posts reviews and must be a different account.

Resolve both once at establishment, in this order: explicit user input,
repository instructions, then host user configuration. Do not ship or infer a
Projector-wide default. If either identity is missing, ask for it. Confirm the
operator with `gh auth status` and confirm the reviewer under the exact token
used for writes:

```sh
GH_TOKEN="$(gh auth token --user <reviewer>)" gh api user --jq .login
```

The result must equal the configured reviewer and must differ from the
operator. Never fall back to the operator when reviewer authentication fails.
Read access can submit a visible review, but repositories requiring an
approval from a collaborator need the reviewer to have write access; verify
that a clean approval changes `reviewDecision` to `APPROVED`.

Watch only the repository containing the current working directory. By default,
track its open pull requests authored by the operator. An explicit request may
add another author or named pull request, but widen scope no further. Hold
validated logins literally in every query; never use `@me`, because its value
changes with `GH_TOKEN`.

## Establish the loop

1. Read repository instructions and applicable review or GitHub workflow
   skills.
2. Resolve the repository, checked-out branch, its pull request, every open
   operator pull request, and the total open count:

   ```sh
   gh pr list --author <operator> --state open --limit 200
   ```

3. Fetch each pull request's base SHA, head SHA, state, reviews, and
   thread-aware review threads. Say how many operator pull requests are tracked
   out of the repository total.
4. Determine the last reviewed SHA from durable GitHub state or the current
   conversation. Review any current head without a completed exact-head review
   immediately; do not baseline it away.
5. Start or reuse a persistent recurring goal that records the repository,
   operator, reviewer, tracked pull requests, and reviewed SHAs.
6. Run the bundled `scripts/watch-prs.sh` with a durable state file,
   `--author <operator>`, `--worktree <repository>`, and an interval of at
   least 30 seconds. Use the host's persistent process or monitor facility.
   Seed only SHAs already reviewed.

The watcher prints `NEW PR`, `NEW HEAD`, `RESPONDED`, `CLOSED`, and
`BRANCH`. Treat `RESPONDED` as a re-review request for a
`CHANGES_REQUESTED` head whose threads are all resolved; it prevents a
body-only response from deadlocking both loops. Keep the loop silent while no
event needs action.

If adopting an existing watcher, fetch unresolved state first, then verify its
state file contains every expected row. Restart it when the script changed
after the process started. Silence alone proves nothing.

## Review an exact head

For every new head:

1. Confirm the pull request remains open and record its full SHA.
2. Fetch that commit and create a scratch worktree at it. Never run a
   reproducer that writes inside the operator's checkout.
3. Confirm the scratch worktree's `HEAD` equals GitHub's recorded SHA.
4. Only then post a concise start comment naming the short SHA, under the
   reviewer token.
5. Inspect both the new range and the pull-request-wide integration diff. Read
   the code and documentation the change depends on.
6. Run focused tests and reproductions proportional to risk. Verify every
   prospective finding against the exact code.
7. Re-fetch the head before publishing. If it moved, revalidate findings and
   review the replacement SHA separately.

Do not invoke a separate Codex, Claude, Bugbot, or other reviewer unless the
user explicitly requests that service. This skill performs the local review.

## Publish one review

Submit actionable findings as inline threads in one review with
`REQUEST_CHANGES`. Each finding names priority, impact, and the verified code
path or reproduction. Do not drip-feed findings or use ordinary issue comments
for them.

When no findings remain, submit `APPROVE` with a body naming the exact SHA and
what was checked. Never downgrade either verdict to `COMMENT` to work around
an identity or permission failure. Confirm the thread state, and after approval
confirm that `reviewDecision` is `APPROVED`.

Record a SHA as reviewed only after its review is published and verified.
Never resolve the author's findings, claim a newer SHA was reviewed, or merge.

## Gate readiness claims in plans

A plan's `status: now` is an executable-readiness claim. On a pull request
whose substance is a plan, or one that changes a plan from `next` or `later`
to `now`, every question introduced or changed by that pull request must be
answered or explicitly deferred to implementation. A readiness flip owns every
question still open at the flip, even if the questions predate the diff.

An owned unresolved question is a blocking inline finding. A pre-existing
question on a plan already at `now` is noted in the review body rather than a
thread, because this change did not introduce the blocker. A question explicitly
answered by building the implementation does not block.

Plans at `next`, `later`, or `done` make no executable-readiness claim, so
their open questions do not withhold approval. Name the status and questions in
the review body so the exemption is visible. Resolve status from the nearest
project's lowercase `readme.md`; supplemental documents carry no independent
status.

## Continue after fixes

Every pushed SHA, including a fix-only SHA, starts a complete review cycle.
Green CI and resolved threads are evidence about state, not substitutes for
review. Drop a pull request when it closes or merges, keep watching later
operator PRs, and continue until the user stops the loop.
