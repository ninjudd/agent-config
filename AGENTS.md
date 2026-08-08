# Personal notes (apply in every repository)

## The `docs/` and `docs/projects/` convention

Several repos (Modal, Fyra, Field, msg) share the same documentation layout, so
its conventions live here rather than drifting apart in each one. Each repo's
own `AGENTS.md` lists the docs it actually has.

- `docs/` describes how the system works today. Keep it current when behaviour
  changes.
- `docs/projects/` is the work itself: three lists — `now.md`, `next.md`,
  `later.md` — pointing into `all/`, where every plan lives and nothing ever
  moves. Read `docs/projects/README.md` before adding to it.
- Plans are cited by section (`onboarding.md §7`), including from code comments,
  so renumbering a section silently breaks references. Add new sections at the
  end.
- A plan whose status line is stale is worse than one with no status at all.

## Pull requests

**Open pull requests; never merge them.** Merging is my review checkpoint, no
matter how small or docs-only the change is. End the work at `gh pr create` and
hand over the URL. After I merge, sync local main before continuing.

Open them ready for review by default, even when they contain an approved
work-in-progress slice. Use draft status only when the pull request is genuinely
not ready for review and we intentionally do not want it reviewed yet. Do not
use draft status merely because more work is planned.

My repos are configured alike, and the ruleset is what enforces all of the
above: main takes no direct pushes, history stays linear, every review thread
must be resolved before a merge, and merges are squashed with the PR title and
body taken as the commit message verbatim. So write the title and body as the
commit message they are about to become — title in the imperative, body
explaining why rather than what.

That collides with the wrapping rule at the end of this file, and the wrapping
rule wins. PR bodies go up unwrapped, so the squashed commit message inherits
long unwrapped paragraphs: worse in `git log`, better everywhere the text is
actually read. Never hard-wrap a PR body to tidy the commit it becomes.

## Pull request reviews are local by default

When I ask to "review this PR" (or equivalent), review the checked-out pull
request yourself: resolve its exact head, inspect the local diff and the code it
depends on, and verify every finding. A generic review request does **not**
select or authorize a separate Codex or Claude reviewer.

**Local means where the reviewing happens, not where the findings land.** Post
them to GitHub as inline review comments on the lines they concern — a review
summarized only in the terminal is not a review anyone else can act on, and it
leaves nothing to reply to or resolve later. Findings posted that way become the
same review threads the section below governs, so the two halves fit together:
you post the finding, then the fix reply and the resolve close it out.

Codex and Claude CLI reviews are opt-in. Run one only when I explicitly name it
("run a Codex review", "run a Claude review") — that explicit request is what
authorizes sending the repository context needed for the review to the named
service. Use the selected CLI directly; do not start a review with an
`@codex review` comment.

To run one: resolve the pull request head, run the selected CLI against that
exact code, and wait for the CLI process to finish before acting on its results.
CI going green is unrelated to review completion. Keep me updated about once a
minute during longer review runs.

## Finish a review finding by resolving its thread

Review findings arrive as inline review comments — Codex, Claude, and Bugbot all
attach them that way — so they live in threads that issue-comment APIs never
show. Fetch them thread-aware:

```
gh api graphql -f query='query { repository(owner:"<owner>",name:"<repo>"){
  pullRequest(number:<n>){ reviewThreads(first:60){ nodes{
    id isResolved path line comments(last:1){nodes{author{login} body}} } } } } }'
```

Then, per finding:

1. **Verify the claim against the code before acting on it.** The bots are
   usually right, and occasionally right about the wrong reason. When the
   reasoning does not hold but the fix does, say so plainly in the reply.
2. Implement and validate the fix, then commit and **push to the PR branch**.
3. **Reply in the thread** with the disposition — fixed, deferred,
   non-actionable, needs clarification — naming the commit.
4. **Resolve the thread.** None of these bots resolve their own threads after a
   later push, so an unresolved thread is not a signal that anything is
   outstanding.
5. Re-fetch `reviewThreads` and confirm `isResolved: true`.

That order matters: push, then reply, then resolve. The ruleset requires every
conversation to be resolved, so resolving is literally what unblocks a merge —
one unresolved thread holds it. Treat resolving as an assertion that the branch
already carries the fix.

Which is the reason to resolve them, not a reason to act on the unblocking.
Resolving does not change who merges — that is still me.

**Never resolve a finding that was not fixed.** Explain the disposition and
leave it open.

Steps 3–5 are part of fixing a finding, not a separate favour to ask for. Don't
leave threads open pending permission.

**Only the first push is reviewed automatically.** Bugbot reviews that one.
Nothing after it is automatic anywhere — not a later push, not marking a draft
ready, and not the push carrying the fixes for the findings. So never wait on a
review that isn't coming, and never describe one as pending or in progress.

Fixes can introduce regressions, so decide deliberately whether a fresh review
is warranted after a batch — but not after every batch. Request one for P0/P1
fixes, broad refactors, schema or protocol changes, or changes spanning
interacting components. Decide case by case for P2. Normally skip it for narrow,
well-tested P2/P3 fixes that add no significant behaviour. When one is warranted,
run the Codex or Claude CLI directly against the current head, rather than asking
for it with an `@codex review` comment. Make sure it covers the head you mean: a
review of an earlier commit says nothing about the commits after it.

## Don't hard-wrap text written *to* GitHub

PR descriptions, issue bodies, and review comments render with GitHub's
hard-line-break extension: every single newline inside a paragraph becomes a
literal `<br>`. Wrapping that text at 72–80 columns produces visibly ragged
output — one short line after another, exactly as typed.

So write those as unwrapped paragraphs, one line per paragraph, however long.
Use real newlines only where they are structural: headings, list items, table
rows, code fences.

Markdown *files* in a repo are the opposite case. They follow CommonMark, where
a single newline inside a paragraph is just a space — so hard-wrapping is
invisible when rendered, and it keeps a one-word edit to a one-line diff. Match
whatever wrapping a repo's docs already use; don't reflow them.

Commit messages are a third thing again: not rendered as Markdown at all, so
this rule says nothing about them — with one exception that matters here. A
squashed merge takes the PR body verbatim, so on these repos the PR body *is*
the commit message, and it ships unwrapped. Wrap a commit message you write
yourself; never wrap a PR body to control what the merge produces.

Check a body that's already posted, rather than assuming:

```
gh api repos/<owner>/<repo>/pulls/<n> \
  -H "Accept: application/vnd.github.html+json" --jq .body_html | grep -c '<br>'
```

Any `<br>` in a prose paragraph means the body went up hard-wrapped. Fix it by
rewriting the body with `gh pr edit <n> --body-file <file>`.
