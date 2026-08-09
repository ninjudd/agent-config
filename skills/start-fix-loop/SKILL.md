---
name: start-fix-loop
description: Watch every open pull request for incoming review findings, verify each against the code, fix it, push, reply in its thread, and resolve it — running in the background alongside other work until the user stops it. Use when the user invokes /start-fix-loop or asks to watch for reviews and act on them, keep fixing review comments as they arrive, or drive pull requests to a clean review.
---

# Start Fix Loop

Run a standing loop on the author's side of a review: watch every pull request in the tracked set, fix findings as they arrive, and close their threads. This is the counterpart to `start-review-loop`, which produces the findings this skill consumes.

**It keeps running.** A clean review is a status to report, not a reason to stop — new findings arrive on later pushes, and new pull requests join the set as they open. It runs in the background while other work goes on, and comes down only when the user stops it.

Treat "fixed" as an externally visible assertion. Resolving a thread tells everyone the branch already carries the fix, and the repository ruleset treats resolved threads as what unblocks a merge, so resolve only what is genuinely fixed and pushed.

## One repository: the one you are in

The loop watches **only the repository of the current working directory** — every open pull request in *that* repository, and never a sibling checkout. Another agent is very likely running its own loop there, and two agents fixing one pull request race each other's pushes and each other's thread replies.

A request to "also cover" another repository is a request to run this skill **there**, in a session whose working directory is that repository. Say so rather than widening this loop's scope.

## Establish the loop

1. Read the repository's `AGENTS.md`, `CLAUDE.md`, and any applicable review or GitHub skills. The user's own conventions outrank anything here.
2. Resolve the repository and **every open pull request**, not only the checked-out branch's. Each one's number, base branch, head SHA, and review threads are the tracked set. If nothing is open, say so and watch for the first one rather than inventing a target.
3. Record each head SHA and each pull request's `reviewDecision`, and baseline **only the already-resolved threads**, so settled findings are not re-litigated. A `reviewDecision` of `CHANGES_REQUESTED` at establishment is outstanding work for the same reason an unresolved thread is — somebody asked for changes and nobody has withdrawn the request — and it is never baselined away, whether or not any thread accompanies it. Never baseline an unresolved one. Resolved means somebody decided; unresolved means outstanding work, whether it arrived a second ago or before the loop existed. A baseline of "every thread that exists right now" silently swallows every finding already waiting — the loop then runs perfectly and fixes nothing.
4. Note which pull requests are stacked on others. A finding about code that belongs to a base PR is fixed on the base branch, not duplicated onto the child — see "Stacked pull requests".
5. **Arm the watcher now, before fixing anything.** It *is* the loop; the rest of this skill is only what to do when it fires. Start it as soon as the baseline exists, confirm it is actually running, and say so. A baseline gathered and a finding fixed are not a loop — they are one pass, and a pass ends.
6. **Prove it fires before trusting it.** A watcher that has never emitted anything looks exactly like a watcher that cannot. Compare its first output against the unresolved threads you just fetched by hand: it should name every one of them. If it reports nothing while unresolved threads exist, it is broken — fix it now, because from here on you will be reading its silence as good news.
7. Do not post anything to GitHub merely because the loop started.

**Armed first, and stays armed.** The failure this ordering exists to prevent is the quiet one: a finding is waiting, or the user reports a live bug, so that gets taken first — every step defensible, the watcher never started, and the loop only ever runs once. Foreground work is expected and is never a reason to defer arming. If the watcher is running, work freely; if it is not, start it before anything else.

**If the watcher stops, restart it.** Its ending is not the loop's ending — only the user ends the loop. When a monitor times out, dies, or stops for any reason other than the user saying so, re-arm it and re-baseline against the threads as they now stand. **Check first that one is not already running** — a watcher that survived whatever you thought killed it is still delivering, and arming a second on top of it doubles every notification for this repository, which reads as a burst of new findings rather than as duplicates. Check with `pgrep -f "watch-threads.sh.*<owner>/<repo>"` before starting, not after wondering why everything arrived twice — and scope it to the repository, because a bare `pgrep -f watch-threads.sh` matches the watchers other sessions are legitimately running for other repositories, and reports a conflict that is not one. And when asked what the loop is doing, check that it is genuinely alive before answering rather than inferring it from having started one earlier.

## Wait for findings

- Run `scripts/watch-threads.sh` (beside this file) under `Monitor` with `persistent: true`; do not busy-poll and do not hand-roll a replacement. It takes `--repos owner/a,owner/b`, a `--state` path, an optional `--interval` (default 60, floored at 30) and an optional `--renotify` (default 900), and prints one `FINDING` line per unresolved thread and one `VERDICT` line per open pull request sitting at `CHANGES_REQUESTED`, across every open pull request in those repositories, staying silent when nothing is outstanding.
- **A verdict is outstanding work even with no thread under it, and this is the failure that hides best.** A reviewer may put every finding in the review summary body and open no inline thread at all, and then a thread watch is correctly silent while the pull request is blocked. Silence is what this loop reads as "nothing to do", so the pull request is reported clean and stays that way. `VERDICT` lines exist for exactly that case; they carry the reviewed SHA, and are keyed on reviewer and SHA so a re-review of a new head announces at once rather than waiting out `--renotify`.
- It is level-triggered by construction, which is the requirement below rather than an implementation detail: it reports what is currently unresolved, re-announcing anything still open after `--renotify` seconds, and it rebuilds its state from the live thread set so a resolved thread simply falls out. A failed query carries its rows forward rather than retiring them, so a blip cannot silently drop a live finding.
- Poll no more often than every 30 seconds, and tolerate transient API failures without ending the watch.
- **Watch for what is unresolved, not for what is new.** Those come apart precisely when it matters: a thread posted while the watcher was being set up, during a network blip, or before the loop started is not new, and a watch that only reports transitions never mentions it again. Report the outstanding set, suppress what you have already picked up, and re-announce anything still unresolved periodically. An edge-triggered watch loses a finding permanently the one time it misses an edge; a level-triggered one is merely repetitive, which is the cheaper failure by far.
- Findings arrive as **inline review threads**, which issue-comment APIs never show. Fetch them thread-aware:

```
gh api graphql -f query='query { repository(owner:"<owner>",name:"<repo>"){
  pullRequest(number:<n>){ headRefOid reviewThreads(first:60){ nodes{
    id isResolved path line comments(last:1){nodes{author{login} body}} } } } } }'
```

- Watch **every tracked pull request**, not just one. Poll the open set rather than a fixed list of numbers, so a pull request opened later joins on its own and a merged one drops out.
- Watch for unresolved threads that are new since the baseline, and for review summary comments naming a SHA.
- **CI state is independent.** A green check is not a review, and a red one is not a finding. Handle failing CI only if the user asked for that too.
- **Do not wait for a review that is not coming.** Only the first push is reviewed automatically, and by Bugbot alone; nothing after it is automatic unless a reviewer loop is watching. If a push draws no review activity within a few minutes, report that plainly and ask whether to keep waiting, rather than idling indefinitely.

## Fix one finding at a time

For each unresolved finding, in the order posted:

1. **Verify the claim against the code before acting on it.** Reviewers are usually right, and occasionally right about the wrong reason. If the reasoning does not hold but the fix does, say so plainly in the reply. If the finding is simply wrong, do not fix it — see "Findings you decline". If it is right that something is broken but the choice of fix is the user's, stop and ask rather than picking one to keep the loop moving.
2. Reproduce it. A finding worth fixing is worth a failing test, an error message, or a measurement that shows the defect exists.
3. Implement the fix, matching the surrounding code's idiom, comment density, and naming. **Before inserting at an anchor, read the lines immediately above it.** An anchor is usually the first line of something, and inserting "before" it lands inside whatever precedes it: an anchor below a `#[test]` or `@override` attribute absorbs the attribute, and one inside a doc comment splits the comment around the new code. Both compile, and the first silently stops running a test while leaving the suite green — a passing suite is not evidence the insertion landed where it was meant to.
4. **Prove the regression test catches it.** Run the new test against the unfixed code and confirm it fails, then restore the fix. A test that passes either way documents nothing.
5. Run the repository's full validation gate — its tests, linter, and formatter, whatever `AGENTS.md` names — before pushing anything.
6. Keep each finding's fix in its own commit where they are independent, so a reply can name the commit that carries it.

Batch related findings into one pass when they touch the same code, rather than pushing once per comment.

## Commit, reply, push, resolve — in that order

The order is not cosmetic, and the two halves have different requirements. A reply only needs the commit to *exist*, so it can go up before the push. Resolving asserts that the branch already carries the fix, so it cannot.

1. **Commit locally**, after the validation gate passes. The SHA now exists and is final, which is all a reply needs to name it.
2. **Reply in the thread** with the disposition — fixed, deferred, non-actionable, needs clarification — naming that commit. Say what was verified and what the fix cost, not just that it is done.
3. **Push to the PR branch.** Never to the base branch, and never merge the PR.
4. **Resolve the thread.** No reviewer bot resolves its own threads after a later push, so an unresolved thread is not a signal that anything is outstanding.
5. **Re-fetch `reviewThreads` and confirm `isResolved: true`.** Do not take the mutation's word for it.

Replying before the push is the point of this ordering: the push is what triggers the next review, and a reviewer that arrives after it should find the reasoning already there rather than a bare new head. Push promptly afterwards — a reply naming an unpushed commit is briefly untrue, and the window should stay short.

If the push fails, say so in the thread immediately and leave it unresolved. An unresolved thread is the visible signal that something is incomplete, which is exactly why resolving waits for the push to land.

When a rebase renames the commits, name the SHA on the branch that owns the fix, and re-read it after the rebase rather than quoting the pre-rebase one.

Replies and PR bodies render with GitHub's hard-line-break extension, where every newline inside a paragraph becomes a literal `<br>`. Write them as unwrapped paragraphs, one line per paragraph, however long.

If the PR body no longer describes what the branch does — a squash merge takes it verbatim as the commit message — update it to cover the new commits.

**A fix commit dates the description, and the Testing section goes stale first.** Test counts, enumerated test names, line numbers, and "you should see" output are all claims about the branch as it was when the body was written, and each fix quietly falsifies some of them: "five new tests" becomes six, a named test gets renamed, output gains a line. None of it fails loudly — the reader finds out by running a command that no longer matches. Re-read the Testing section after each batch of fixes rather than only before handing over, and re-run the commands it names, because a command that errors in a pull request body is worse than no instructions at all.

## Findings you decline

**Never resolve a finding that was not fixed.** Reply with the reasoning, leave the thread open, and tell the user it is open and why.

An open declined thread blocks the merge and is the user's call to make, so the loop does not spin waiting for it to clear itself. When every remaining unresolved thread on a pull request is one you declined, that pull request is handed over — keep watching the rest.

## A clean review is a report, not an end

When a verdict reports no findings **and** names a pull request's current head, and no unresolved threads remain on it, **and** its `reviewDecision` is not `CHANGES_REQUESTED`, that pull request is clean. All four, and the fourth is the one that gets skipped: threads are the visible half, so a pull request whose every thread is resolved looks finished, and a review whose findings lived in its summary body leaves nothing to resolve in the first place. Check `reviewDecision` against the current head rather than inferring it from the threads. Say so — the head SHA, the findings fixed with their commits, anything declined, the validation results — and **keep watching**. Clean is a state a pull request passes through, not a terminus: the next push starts another review, and the user has not merged it yet.

A clean verdict for a superseded SHA says nothing about the head that replaced it. Re-fetch the head before calling anything clean.

**A `CHANGES_REQUESTED` that outlives the fixes is a wait, not a fix, and sometimes it is a deadlock.** Once every thread is resolved and the work is pushed, the verdict stands until the reviewer looks at the new head; there is nothing left here to do but wait for that. The case to catch is the one where nothing will ever trigger it. A review loop watches for pushed heads, so a fix that produced no push — a correction to the pull request body, a finding answered in a reply, a finding declined — draws no re-review, and the pull request sits at `CHANGES_REQUESTED` with no unresolved thread and no pending work: not clean by the rule above, and not fixable by anything this loop can do. Say so plainly and hand it to the user rather than waiting on it. Do not manufacture an empty commit to trip the reviewer; that fakes the signal instead of reporting the gap.

Drop a pull request from the tracked set when it merges or closes. Keep the loop itself running for the rest, and for ones opened later.

## When the loop actually comes down

- **The user stops it.** This is the ordinary ending, and the only one that needs no justification.
- **Nothing is open is not a reason to stop.** An empty set is an idle state, not an ending: the watch rediscovers the open pull requests each pass, so the next one opened joins on its own. Say the set is empty once, then stay quiet until something appears.
- **A finding needs the user.** It turns on a decision that is theirs — which of two behaviours is correct, whether a documented promise or the code implementing it is the wrong one, whether a fix is worth its cost, whether a reviewer's premise about the product is right. Stop work on *that* finding, ask, and keep watching the others. Replying "needs clarification" in a thread is a note to the reviewer, not a substitute for asking the user; a loop that guesses in order to keep running produces work nobody asked for and threads that assert something untrue.
- **A finding recurs after being fixed and resolved**, which means the fix was wrong or the review is thrashing. Do not fix it a second time without saying so.
- **The validation gate fails in a way the fix cannot resolve.** Report the failure; do not push past it.
- **Every remaining thread on a pull request is one you declined.** That pull request is the user's call now; keep watching the others.

That list is not exhaustive. Running unattended is a convenience, not an instruction to proceed without an answer you actually need — being stuck and honest about it beats being wrong and finished.

## Running alongside other work

The loop is background work, and the foreground belongs to whatever the user is doing.

- **Never switch branches over uncommitted work.** Fixing a finding means checking out the branch that owns it, and the user may be mid-edit somewhere else. If the worktree is dirty, say what arrived and wait, or use a separate worktree — never stash or discard to make room.
- **Finish the thought you are in.** A finding that lands mid-task is not an interrupt to obey instantly. Reach a coherent stopping point, then take it.
- **Report arrivals briefly.** A finding landing is worth a sentence, not a recap of the whole loop. Save the detail for when it is fixed.
- **Say which pull request you are talking about** whenever more than one is tracked. "Fixed" means nothing when three are in flight.

## Never

- Never merge the pull request. Merging is the user's review checkpoint, however small the change.
- Never resolve a thread on the reviewer's behalf without a pushed fix behind it.
- Never claim a review is pending or in progress when nothing is running, and never say the loop is watching when its monitor has stopped.
- Never discard or overwrite the user's uncommitted work to make a fix land.
- Never invoke an external Codex, Claude, Bugbot, or other reviewer unless the user explicitly names it. This skill consumes reviews; it does not order them.

## Stacked pull requests

Setting the child's base to the parent's branch is the smallest part of stacking and does not make a stack. Follow the user's own conventions for creating one — GitHub supports stacks natively — and keep stack scaffolding out of the PR body, which becomes the squashed commit message.

When the PR is based on another open PR:

1. Fix a finding on the branch that owns the code — the base PR's branch if the code is the base PR's.
2. Rebase the child branch onto the updated base and force-push with `--force-with-lease`.
3. Re-run the full validation gate on the rebased child; a clean base does not vouch for it.
4. Reply and resolve on the PR whose thread the finding is on, naming the commit even though it lives on the other branch.

**When the parent merges, check where the child now points.** GitHub moves a child's base automatically only when the parent's branch is *deleted* on merge. Otherwise the child still points at a branch that is now dead, and merging it puts the work somewhere nobody is looking instead of into the default branch. Merging the parent "first" does not prevent this and is not a mitigation.

Whether the deletion happens is a **repository setting**, not a ruleset rule: `delete_branch_on_merge`, shown as "Automatically delete head branches" under Settings → General → Pull Requests. Read it rather than assume it — `gh api repos/<owner>/<repo> --jq .delete_branch_on_merge`. On a repository where it is true, the retarget happens on its own and the job here is to confirm it did. Where it is false, the retarget is manual and is the failure mode above waiting to happen.

Where the `gh-stack` skill is installed, `gh stack sync` is the command for this: it detects a squash-merged parent, replays the remaining branches with `git rebase --onto`, and pushes. Follow that skill's rules — but never its merge step, if the user's own conventions reserve merging for them.

When it has to be done by hand, that is `gh pr edit <child> --base <default>`, then `git rebase --onto <default> <old-parent-head> <child>` so only the child's own commits replay, then re-run the gate and force-push. Confirm the result rather than assuming — the child's base should read as the default branch, `mergeable` should be true, and the default branch should be an ancestor of the child's head.
