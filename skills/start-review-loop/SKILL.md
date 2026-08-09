---
name: start-review-loop
description: Monitor a GitHub repository's active pull requests and checked-out branch, discover newly opened PRs after branch changes, review each exact pushed SHA locally, and post verified findings to GitHub. Use when the user invokes /start-review-loop or asks to watch, monitor, or repeatedly review current and subsequent PRs whenever branches or commits change.
---

# Start Review Loop

Run a persistent, exact-head review loop for the repository's tracked PRs and checked-out branch. Treat “review started” as an externally visible assertion: post it only after an unreviewed SHA exists and its local review is actually beginning.

## Post as minjudd

Every write to GitHub — start comments, inline review threads, completion comments, thread replies — goes as the GitHub account `minjudd`, never as the operator's own account. A pull request's author cannot approve or request changes on their own pull request, so a review posted from the author's account can only ever be a comment. Reviewing from a separate identity is what makes the review a real one.

1. Authenticate `gh` as `minjudd` by setting `GH_TOKEN` to that account's token. Prefer an `env` block in Claude Code settings over an `export`: shell state does not persist between tool calls, so an exported variable is gone by the next `gh` invocation.
2. Before the first write of a session, confirm the identity — `gh api user --jq .login` must print `minjudd`. If it prints anything else, stop and report it rather than posting. A review attributed to the wrong account is worse than a late one, and it cannot be un-posted.
3. Re-confirm after anything that could change the environment, including restarting a watcher or resuming after compaction.
4. Reads may run under whichever account is active; only writes carry an identity that matters. A long-running watcher started before the token was set keeps its old environment — harmless while it only lists pull requests, and a reason to restart it before it writes anything.
5. `minjudd` needs access to the repository under review, and how much depends on the repository. Read access is enough to see a pull request, to comment, and to *submit* either verdict. It is **not** enough for an approval to count: where the ruleset requires approving reviews, GitHub answers "no applicable reviews submitted by reviewers with write access" and leaves the pull request blocked with the approval sitting visibly on it. Write access is what makes an approval satisfy the rule. With no access at all, every call fails as though the pull request did not exist. Report either shortfall as a blocker requiring user input; never quietly fall back to the operator's account.

## One repository: the one you are in

The loop watches **only the repository of the current working directory**, and never reaches into a sibling checkout however tempting the coverage gap looks. Another agent is very likely watching that other repository, and two reviewers on one pull request post two start comments and two verdicts for a single SHA — visible to everyone, and confusing in a way that is not obvious to either of them.

A request to "also cover" or "take over" another repository is a request to run the loop **there**, in a session whose working directory is that repository. Say so rather than widening this loop's scope. The same holds for a pull request that merely *mentions* another repository.

## Establish the loop

1. Read the repository's `AGENTS.md` and applicable GitHub/review skills.
2. Resolve the repository, checked-out branch, current PR number, base SHA, head SHA, state, and review threads.
3. Keep a set of tracked open PRs and the last reviewed SHA for each. Determine each PR's last reviewed SHA from the conversation, from prior review comments, or from existing review threads. When that SHA equals the current head, record it as reviewed and wait. Otherwise the current head is unreviewed: review it immediately, exactly as a newly pushed head would be reviewed. Do not baseline an unreviewed head away — a loop that starts by declaring the existing work reviewed reports a review nobody performed.
4. Start or reuse a recurring goal naming the repository, checked-out branch, tracked PRs, and baseline SHAs. Keep monitoring until the user stops the loop; individual PRs leave the set when they close or merge.
5. Do not post anything to GitHub merely because monitoring began. The start comment belongs to a review that is actually beginning, whether that is the head found at establishment or one pushed later.

## Wait for a new head

- Run `scripts/watch-prs.sh` (beside this file) under `Monitor` with `persistent: true`; do not busy-poll and do not hand-roll a replacement. It takes `--repos owner/a,owner/b`, a `--state` path, an optional `--interval` (default 60) and an optional `--worktree` to notice branch changes, and it prints one line per event — `NEW PR`, `NEW HEAD`, `CLOSED`, `BRANCH` — staying silent otherwise. Seed the state file with `<owner/repo> <number> <sha> <ref>` rows to baseline heads already reviewed; leave it empty and every open pull request reports as new, which is what establishing the loop wants.
- The script exists because two failure modes are easy to reintroduce by hand and silent when you do: closure detection must run even when the open-pull-request list is *empty*, since closing the last one is exactly that case; and a failed API call must never be read as "everything closed". Fix bugs in the script rather than working around them at the call site.
- Check both the head of every tracked PR and the repository's checked-out branch.
- While every PR head equals its baseline or last reviewed SHA and the branch is unchanged, remain completely silent: send no commentary or final message to the user and post nothing to GitHub. Resume communication only when a review actually starts or finishes, monitoring state changes, a blocker requires user input, or the user explicitly asks for status.
- Treat CI state as independent. A green check does not mean a review ran or completed.
- Remove closed or merged PRs from the tracked set, but keep the repository loop active for later branch changes and PRs.

## Discover PRs after a branch change

When the checked-out branch changes, or while the current branch has no known PR:

1. Resolve the branch name without modifying the worktree.
2. Look for an open PR whose head is that branch. If none exists yet, wait silently and check again later; do not comment on GitHub.
3. When a new PR appears, add it to the tracked set and treat its current head as unreviewed. Review it immediately rather than baselining it away.
4. Keep previously tracked PRs in the loop until they close or merge, so changing branches does not silently abandon an open review stream.
5. If the repository is detached or on a branch with no PR, continue monitoring without inventing a target.

## Start an exact-head review

When GitHub reports a different head SHA, or branch discovery finds a new PR:

1. Confirm the PR is still open and record the full SHA.
2. Fetch or otherwise resolve that exact commit locally. Preserve dirty user work; never discard or overwrite it to prepare a review. Use a safe separate worktree or inspect fetched objects when necessary.
3. Confirm the local commit equals GitHub's recorded SHA.
4. Only now post a concise PR comment such as `Starting review of abc1234.`
5. Inspect both the newly pushed range and the PR-wide integration diff. Read the code and documentation the change depends on, not only the changed lines.
6. Run focused reproductions and tests proportional to risk. Verify every prospective finding against the exact code before posting it.
7. Finish a complete pass before posting findings; avoid drip-feeding issues that one sweep could find together.

Do not invoke an external Codex, Claude, Bugbot, or other reviewer unless the user explicitly names it. This skill performs the local review itself.

## Publish the result

1. Re-fetch the PR head before publishing.
2. If another push landed during review, never imply the old review covers it. Revalidate prospective findings on the newest head and begin a separate review of that SHA.
3. Post actionable findings as inline GitHub review threads, with priority, impact, and a verified reproduction or code path. Submit them as one review with `event: REQUEST_CHANGES`, so the pull request carries a verdict and not only prose. Do not use ordinary issue comments for findings.
4. If the reviewed SHA has no findings, submit a review with `event: APPROVE` whose body names that SHA and says what was checked. The approval is the completion notice. Do not post it as an ordinary issue comment: a comment records no verdict, leaves the pull request looking unreviewed, and is indistinguishable from someone thinking out loud. On a plan pull request, check the section below before approving — an unresolved question there withholds the approval even when the review turned up no findings of its own.
5. The start marker is the one thing that stays an ordinary issue comment — there is no review to attach it to yet. Everything after it is a review event.
6. Never downgrade the event to work around a rejection. If GitHub refuses `APPROVE` or `REQUEST_CHANGES` — because the reviewing account authored the pull request, or lacks access — stop and report it as a blocker. A review silently posted as a comment claims less than the review that was actually performed.
7. Re-fetch thread-aware `reviewThreads` through GraphQL and confirm the posted thread state. After an `APPROVE`, confirm separately that the approval **counted**: `reviewDecision` must come back `APPROVED` rather than `REVIEW_REQUIRED`. This is a different check from step 6 and catches what step 6 cannot — an approval from an account without write access submits cleanly, refuses nothing, and leaves the pull request blocked, so a loop that skips it records the head as reviewed and goes quiet with the work only looking finished. Two ruleset settings make the check worth repeating rather than doing once: `dismiss_stale_reviews_on_push` discards an approval on the next push, and `require_last_push_approval` requires it to land after the final one.
8. Record the SHA as reviewed for that PR only after the result is published, then immediately check whether a newer head or newly opened branch PR is queued.

Never resolve findings on the author's behalf, never claim a later push was reviewed before inspecting it, and never merge the PR.

## Plan pull requests: an open question withholds the approval

A **plan pull request** is one whose substance is a plan — the plan is the change, not a file the change touches on the way past. A pull request that implements something and updates its plan alongside is an implementation pull request, and this section does not apply to it; review it the usual way. The distinction is what the pull request is *for*, not whether a plan file appears in the diff.

Most of these repositories keep plans in `docs/projects/all/`, but do not key on that path alone — Nio keeps them in `docs/plans/`, and a repository that has neither can still open a pull request whose substance is a plan. The layout is a hint about where to look, not the test.

On one of those, an unresolved question withholds approval on its own, even when the review found nothing else wrong. A plan exists to be executed from, and its open questions are precisely the parts that cannot be executed from yet — approving one asserts the plan is ready while the plan itself says it is not. The verdict on a question the pull request owns — the next paragraph says which those are — is `REQUEST_CHANGES` with an inline thread on it, never an `APPROVE` carrying the reservation in its body, because a caveat inside an approval is not a thing anyone has to answer before merging. That nothing in an approval body binds is exactly why a question the pull request does *not* own belongs there instead: one property, a defect where the question should block and the whole point where it should not.

**Which questions are the pull request's to answer: the ones it introduces or modifies.** A review approves a change, not a document, so a question the pull request never touched is not its responsibility. A question is in scope when the pull request adds it, or edits its text or its disposition. Everything else in the plan is pre-existing: note it in the body of the review, since the reviewer should still say out loud that the plan is not yet executable, but do not withhold the approval over it. Where the change makes a pre-existing question moot or newly answerable, say that too rather than passing over it in silence.

**In the review body, not an inline thread — a mechanical requirement here, not a stylistic preference.** These repositories set `required_review_thread_resolution`, so an unresolved thread blocks the merge exactly as a `REQUEST_CHANGES` finding does, and `start-fix-loop` is instructed never to resolve a finding it did not fix, so the thread will not clear itself either. Post a pre-existing question as a thread and the result is a pull request that is approved and still unmergeable, held on the very question the scope rule just decided should not hold it. The body says the same thing just as visibly and creates nothing that has to be resolved before merging. It also matches what this skill already does everywhere else: inline threads carry findings submitted with `REQUEST_CHANGES`, and a note that deliberately does not block is not a finding.

The stricter reading — any open question anywhere in the plan blocks — is worth naming because "an unresolved question withholds approval" invites it, and it fails in a specific way. `field`'s `automation.md` §3 carries three questions with no disposition. A pull request adding a §4 about something already settled would, on that reading, be held on all three, and the author's cheapest way to clear it is to write dispositions onto questions their change never touched. A disposition written to clear a review is a hedge, so the strict reading manufactures exactly the failure this section exists to catch.

Find the section however it is titled. These repositories write it as `## Open questions`, `## 3. Open questions`, `## Open questions (decide before implementing)`, `## 8 What is unresolved`, and `## 3 Design questions this phase must settle`, so key on what a section does rather than on a literal heading, and read the prose too — a question posed mid-plan counts as much as one in a list. A plan with no such section is not blocked by this; do not go looking for questions to hold one back with.

**The exception is a question the plan deliberately defers to implementation.** Some questions really are answered by building the thing, and a plan that says so is finished rather than unfinished — `msg`'s `daemon-and-permissions.md` keeps a "Resolved by building it, and previously listed here" list of exactly those. A question marked that way does not block approval, and saying it does is the failure in the other direction: it holds a ready plan hostage to a question whose answer the plan has already correctly located in the future.

Deferral is per question, not per section, so read them one at a time. `field`'s `automation.md` §3 gives its first question a disposition — "Leaning yes; decide when speccing" — while leaving the other three with none at all, so those three are still open regardless of what the first one counts as — whether they block a given pull request is then the scope question above, and on one that introduced them they do. Requiring the deferral to be explicit is what keeps this checkable: "resolved by building it" defers, whereas "leaning yes" on its own, "probably", and a question simply left hanging are hedges, and a hedge is the thing this gate exists to catch.

That first question is also the edge worth naming rather than smoothing over. "Decide when speccing" defers to a phase *earlier* than implementation, so it is a deliberate disposition but not the exemption as written, and the exemption is deliberately narrow: a question the plan parks until the work is actually underway. Treat deferral to some other later phase as still blocking, and say so in the thread — if the plan means the question can ride into implementation, that is a one-line edit, and if it means the spec must settle it first then the plan is not yet ready to approve, which is the same answer this gate gives everywhere else. Where a question's disposition is genuinely ambiguous, treat it as open and say in the thread that one line in the plan recording the disposition would settle it — that is a cheap edit for the author and it makes the plan honest about which of its questions are deliberate.

**A pull request that creates a plan is not a special case, and following the rule through shows why it should not be one.** When the pull request *is* the plan, every question in it is one the pull request introduces, so all of them are in scope and a new plan whose questions are bare cannot be approved on its first pull request. That is the intended outcome rather than an artefact of the wording. Creation is the only point at which a plan's readiness as a whole is ever gated: from the next pull request onward those same questions are pre-existing, and nothing blocks on them again. The way to land such a plan is the deferral exception doing its job: mark the questions the plan means to settle by building, and it is approvable.

Answering a plan's open question is usually the author's call rather than the reviewer's, and often the user's rather than either. Post the question as a finding and leave it there; do not answer it in the thread and approve on the strength of your own answer.

## Continue after fixes

Every new pushed SHA—including a fix-only SHA—and every newly discovered branch PR starts another review cycle. Review fixes for regressions and examine the surrounding affected paths. A resolved thread or green CI run is evidence about state, not a substitute for the requested exact-head review.

Between completed review cycles, compact the conversation when context is becoming large. Preserve the tracked PRs, checked-out branch, last reviewed SHA for each PR, unresolved thread state, and exact-head/start-comment rules in the compacted state. Never compact during an active review; publish that review first, then compact before waiting for or beginning the next one. After compaction, re-resolve local and GitHub state before acting.
