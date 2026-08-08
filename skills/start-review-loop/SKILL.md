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
5. `minjudd` needs access to the repository under review. Read access is enough for everything this skill does: seeing the pull request, posting comments, and submitting reviews. Without it every call fails as though the pull request did not exist. Report that as a blocker requiring user input; never quietly fall back to the operator's account.

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
4. If the reviewed SHA has no findings, submit a review with `event: APPROVE` whose body names that SHA and says what was checked. The approval is the completion notice. Do not post it as an ordinary issue comment: a comment records no verdict, leaves the pull request looking unreviewed, and is indistinguishable from someone thinking out loud.
5. The start marker is the one thing that stays an ordinary issue comment — there is no review to attach it to yet. Everything after it is a review event.
6. Never downgrade the event to work around a rejection. If GitHub refuses `APPROVE` or `REQUEST_CHANGES` — because the reviewing account authored the pull request, or lacks access — stop and report it as a blocker. A review silently posted as a comment claims less than the review that was actually performed.
7. Re-fetch thread-aware `reviewThreads` through GraphQL and confirm the posted thread state.
8. Record the SHA as reviewed for that PR only after the result is published, then immediately check whether a newer head or newly opened branch PR is queued.

Never resolve findings on the author's behalf, never claim a later push was reviewed before inspecting it, and never merge the PR.

## Continue after fixes

Every new pushed SHA—including a fix-only SHA—and every newly discovered branch PR starts another review cycle. Review fixes for regressions and examine the surrounding affected paths. A resolved thread or green CI run is evidence about state, not a substitute for the requested exact-head review.

Between completed review cycles, compact the conversation when context is becoming large. Preserve the tracked PRs, checked-out branch, last reviewed SHA for each PR, unresolved thread state, and exact-head/start-comment rules in the compacted state. Never compact during an active review; publish that review first, then compact before waiting for or beginning the next one. After compaction, re-resolve local and GitHub state before acting.
