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
- A project is one file, `all/<name>.md`, until it genuinely outgrows one —
  several phases in flight, a design wanting its own space, a decision log worth
  keeping apart from the plan. Then it becomes a folder, `all/<name>/`.
  Promotion is one `git mv` inside `all/`, so none of this is decided up front,
  and it is the one move the "nothing ever moves" rule above allows.
  `triangle/app` runs fourteen folders against far more single files, which is
  the ratio to expect: reach for a folder when a file is unwieldy, not when a
  project sounds important.
- A folder's entry point is `overview.md`, and that is the only fixed rule
  inside one. It is what the three lists link to, and what carries the project's
  `status:` frontmatter. Everything else is shaped to the work rather than to a
  template: `triangle/app` has grown `design.md`, numbered step documents in
  execution order, `decisions.md`, `progress.md`, a `post-mortem.md`, and
  `impl/` or `reviews/` subfolders, but each emerged from a particular project
  and none is required. Add a document when there is something to put in it.
- Promoting a file to a folder breaks every inbound reference to
  `all/<name>.md`, which is now `all/<name>/overview.md`. The promoting pull
  request sweeps them in the same diff; `rg -n 'all/<name>\.md'` finds them,
  and code comments cite these paths, so this is not only a docs concern. Use
  `rg` because it skips `.git` and gitignored build output wherever it runs,
  which a plain `command grep -r` does not — minutes rather than a moment on a
  tree the size of `triangle/app`. Do not expect that gap to reproduce in a
  Claude Code session: `grep` is shimmed there to an ignore-aware binary and
  is the faster of the two, so the rule is about behaving the same everywhere
  rather than about speed here. Cite into a folder the same way as into a
  file — `all/passkey/design.md §4` — and the section-numbering rule above
  applies unchanged.
- Every project in `all/` carries YAML frontmatter with `status:` — on the file
  when it is a file, on `overview.md` when it is a folder, where it is the
  status of the whole project and the documents beside it need none of their
  own. `triangle/app` bears out the "one place" half exactly — thirteen of its
  nested documents carry a status keyword and they are exactly its thirteen
  `overview.md` files, so nothing beside an overview has ever carried one — but
  not the entry-point half, and the gap is the honest reason to state this as a
  rule rather than describe it as practice. Three of its fourteen folders keep
  a root `design.md` and no `overview.md`: `invite-codes` and
  `survey-adjustment` push theirs down to `impl/overview.md`, and `doctor-scan`
  carries no status anywhere, which is a folder-shaped project the rule above
  says cannot exist. None of the three is on any of the lists, so they are past
  work nobody is going back to fix. It is also what the review gate reads, so a
  folder-shaped project has one answer to "is this plan claiming readiness"
  rather than one per document. The keyword is one from a fixed set, adopted
  from the same repo: `Draft` (written, implementation not started), `Active`
  (in progress), `Blocked` (waiting on a dependency or decision), `Stalled`
  (lost momentum, not formally dropped),
  `Shipped`, `Superseded`, `Abandoned`, `Reference` (a standing document with no
  build lifecycle). Add `owner:` only where a repo has more than one person to
  ask. The keyword is the state of record; the *why* stays prose in the body, so
  a repo's old `**Status:**` line keeps its story and the frontmatter carries
  the claim.
- Three of those keywords claim the plan is executable — `Active`, `Blocked`,
  `Shipped` — and five claim nothing of the sort. That split is load-bearing:
  open questions in a plan carrying one of the five do not block its pull
  requests from merging, which is what lets a plan be written down before it is
  settled, be abandoned with its questions unanswered, and lets a `Reference`
  document whose substance *is* its open questions exist at all. The pull
  request that flips a plan into one of the three is the one making the
  readiness claim, and it answers for every question still open at that
  moment — usually the pull request that starts the implementation, since
  `Draft` to `Active` is the moment work begins and the frontmatter rides the
  diff that changes it. The review mechanics live in the start-review-loop
  skill; this bullet is why they are shaped that way.
- A plan whose status frontmatter is stale is worse than one with no status at
  all.
- The lists and status frontmatter ride the pull request that changes what they
  say. The one that completes a plan sets `status: Shipped` and edits `now.md`
  in the same diff, so the squash lands code and docs as one commit; a plan
  delivered in slices closes in its last one, not its first. What the `now.md`
  edit *is* varies by repository, so read the file rather than assuming: `msg`
  empties the list back to "Nothing in flight.", while `modal`, `field` and
  `fyra` deliberately keep the shipped line and attach the condition for
  removing it later. Do not plan a separate close-out pull request after the
  merge — it spends a review cycle saying what the merge already said.
  Correcting one that was genuinely forgotten is a different thing and is fine.

## Docs are written in Google developer documentation style

Write `docs/` in the register of the Google developer documentation style
guide (https://developers.google.com/style): second person, present tense,
active voice, sentence-case headings, code font for identifiers and commands,
short task-oriented sections, and an example or command transcript wherever
one beats another paragraph of prose. Adopted 2026-08-10 after comparing
registers (ASD-STE100 → ISO 24495-1 plain language → this) on Field's sends
design; this one kept the precision without the stiffness.

Moving forward only: new documents and new sections use the style, and a
document being substantially revised converts as part of the revision.
Existing docs get a cleanup pass later — do not reflow or rewrite one you are
not otherwise changing. `docs/projects/` keeps its own structural conventions
(numbered cited sections, the status frontmatter each project carries, decision
records with rejected alternatives); the style governs the prose inside them,
not their shape.

Chat gets a different mix. Explain a complicated concept in ISO 24495-1
plain language: prose organized around what the reader needs, leading with
what the thing is and what they do with it, ordinary paragraphs, no headings
or callouts — document scaffolding reads as a manual page dropped into a
conversation. When an example is warranted — and a short one often beats a
third paragraph of abstraction — render it the Google way inside that prose:
a fenced snippet or command transcript with real names and code font for
identifiers, without importing the rest of the page furniture along with it.
The prose carries the explanation; the Google treatment carries the examples
embedded in it.

When the content is a list, write a list — in any of these registers, chat
included. Four items of the same shape, one per project or finding or blocker,
are a list whatever punctuation they arrive in, and running them together as a
paragraph makes the reader re-derive boundaries the writer already knew. Give
each item a short lead-in naming the thing, then its explanation in full
sentences: the bullet buys the scan, and the sentences keep what clipped
fragments would drop. A list is not the scaffolding the paragraph above turns
down — headings and callouts impose a document's shape on a conversation,
while a list is the shape the content already has. The test is whether the
items are parallel and enumerable, not whether there are several of them: an
argument moving through three steps is prose, and cutting it into bullets
loses the connective tissue that made it an argument.

Prose written to GitHub — pull request bodies, issue text, review comments —
is a third kind, and takes this section's *structure* rather than the chat
register's: headings, code font for identifiers and commands, and an example or
command transcript wherever one beats a paragraph. It is written to be scanned,
returned to and acted on rather than read once, and this file already requires
scaffolding in it: every description closes with a **Testing** section, which
is exactly the furniture the chat register turns down. So read "no headings or
callouts" as a rule about talking to a person, not about anything that renders
on GitHub.

Voice does not come with it, at least not into a pull request body, because the
squash turns that body into a commit message: the rule below wins there —
imperative title, and prose explaining why rather than what — over the second
person, present tense and task-oriented sections the `docs/` register asks for.
A body argues where a document instructs, and the two cannot both be the rule
for the same text. Issue comments and review comments carry no such constraint
and can take the register whole. How any of it wraps is a separate question
again, answered by the hard-wrapping rule near the end of this file.

## Pull requests

**Open pull requests; never merge them.** Merging is my review checkpoint, no
matter how small or docs-only the change is. End the work at `gh pr create` and
hand over the URL. After I merge, sync local main before continuing.

Open them ready for review by default, even when they contain an approved
work-in-progress slice. Use draft status only when the pull request is genuinely
not ready for review and we intentionally do not want it reviewed yet. Do not
use draft status merely because more work is planned.

**Lean toward medium-to-large pull requests, not small-to-medium.** Reviewing
one costs real effort, and that effort is charged per pull request *and per
review cycle* while barely moving with diff size: resolving the exact head,
building, running the suite, probing the claims and writing the review cost
about the same for twenty lines as for three hundred. Two small pull requests
therefore cost roughly twice what one medium one carrying both does — and a
second review cycle on a single pull request is cheaper than a second pull
request, which is the counterintuitive half, because the instinct is to split
precisely to avoid another round.

So combine by default, and let splitting be the thing that needs an argument.
Phase chunks and plan sections are for sequencing thought, not for sizing pull
requests: two changes citing different plans belong together when they share a
rationale, when one is unusable until the other lands, or when verifying the
second means re-running the first. What replaces line count as the ceiling is
reviewability — too big is when a reviewer would be holding two unrelated
arguments at once, or when one half would still be worth shipping if the other
were abandoned. That second test is about independent value, not about what
lands first, and the examples below turn on the difference.

Short of that ceiling, fold the follow-on into the pull request that unblocked
it: the one-file move, the doc sweep, the retirement its predecessor made
possible. Each of those could technically go out on its own, which is why the
weaker reading of the ceiling would split them, and none is worth anything
alone — a sweep documenting a change that has not shipped, a retirement of
something still in use. That is sequencing, not independence, and sequencing is
not a reason to split. A five-file, twenty-insertion pull request split off
only because it belonged to a different plan's chunk is the shape to stop
producing — its one claim could not be verified without the pull request
underneath it, so the review had to hold both anyway.

Folding in is not blocked by the rule that work ends at `gh pr create`. What
that reserves is the merge, not the branch: a pull request under review still
takes commits — it is how findings get fixed — so a follow-on belonging to
the same argument goes onto the same branch, costing the extra review cycle
this section already argues is cheaper than a second pull request. Say in the
description that the scope grew, because pushing dismisses any approval
standing against the old head, and that dismissal is the cost being spent.

An *unrelated* change found after the push is the other half of the ceiling,
and it is what stacking is for: folding it in would put a second argument in
front of a reviewer already holding one, so it becomes its own pull request,
stacked on the first where it depends on it. That is not licence to push a thin
pull request and stack the rest behind it. Sizing is settled before opening —
the first one still has to have been big enough on its own — and stacking only
handles what genuinely arrives afterwards. Once I have merged, the predecessor
is gone and the follow-on is simply its own pull request: the ordinary case,
not a failure of this rule.

More generally, that ceiling is the test for whether to stack at all, not only
for work that arrives late: a stack is the right shape exactly when work
crosses it and therefore cannot be one pull request. This section decides
*whether* to stack and the section below decides *how*. It
governs the vendored `gh-stack` skill too, whose upstream text triggered
stacking on wanting small pull requests and treated a change's own tests and
documentation as a separate layer. Those lines are edited to point back here.
Its rule 7 is left as upstream wrote it, because dependency order decides what
order the layers go in without deciding that there is more than one.

My repos are configured alike, and a ruleset covers some of the above but not
most of it, so do not read it as backing everything it follows. What it
requires: main takes no direct pushes, history stays linear, every review
thread must be resolved before a merge, and merges are squashed with the PR
title and body taken as the commit message verbatim. What it cannot: never
merging, the draft policy, and every sizing judgement above are conventions I
check by hand — which is exactly why the merge is my checkpoint rather than
something I could delegate to GitHub. So write the title and body as the commit
message they are about to become — title in the imperative, body explaining
why rather than what.

Required is not the same as guaranteed, and the gap is wide enough to have
mattered here. I hold bypass permission and use it: #11 merged four seconds
after a reviewer opened three threads on it. A fourth landed nine seconds
later again, from a review already being written when the merge went through
— not a bypass at all, but a race, and one that can catch someone who never
bypasses anything. Dismissal on push is real — a push to this pull request
dismissed a standing approval — but it did not fire when #6 was force-pushed
during a rebase, and a stored approval's recorded commit can later move to the
new head on its own, which defeats reading that commit back at submission
time. So check the state rather than inferring it from the configuration, and
do not build an argument on a rule being mechanically enforced.

That collides with the wrapping rule at the end of this file, and the wrapping
rule wins. PR bodies go up unwrapped, so the squashed commit message inherits
long unwrapped paragraphs: worse in `git log`, better everywhere the text is
actually read. Never hard-wrap a PR body to tidy the commit it becomes.

### Every PR body ends with how to try it

Close each description with a short **Testing** section: the exact commands to
run, in order, and what a person should see. Copy-pasteable — real label names,
real paths, no placeholders to fill in — and run them yourself first, from the
directory you tell me to run them from. A command in a PR body that errors is
worse than no instructions, because I find out by hitting the error.

Say plainly what needs building or installing first (`pnpm build` so the `field`
on my PATH is current, `field setup <worker>`, a native rebuild), and what state
it leaves behind — a spawned daemon, generated files, a modified checkout.

Name the thing that would show the change is *wrong*, not only the happy path.
"You should see X" is a demo; "before this you'd get Y here" is a test. Where a
change cannot be exercised by hand — a protocol version bump, a stale-daemon
guard — say that instead of inventing a ritual, and point at the test that does
cover it.

If a command in the section is not the one I would naturally reach for, that is
worth noticing rather than documenting around: I typed `field --version` for the
version report and got the bare number, which was the design working as written
and the wrong design.

## Stacked pull requests

Setting the second pull request's base to the first branch is the smallest part
of stacking, and on its own it produces two pull requests that merely share a
pointer. **Make it an actual stack**, which GitHub now supports natively —
stacked pull requests entered public preview on 2026-07-30, so this is a real
primitive rather than a convention to imitate.

**Create it as a stack.** The CLI is an official extension and is not installed
by default: `gh extension install github/gh-stack`, then `gh stack init <name>`,
`gh stack add <branch>`, `gh stack submit --auto --open`. `--open` is the
load-bearing one: an unattended run is already in auto mode whether or not the
flag is typed, and auto mode creates every new pull request as a **draft**
unless `--open` is passed, which the ready-by-default rule above forbids.
Nothing in the output says "draft", and running the command by hand does not
reproduce it, because the interactive editor defaults to ready for review. Pass
`--auto` anyway, so the behaviour does not change if the terminal turns out not
to be what you assumed. Everything else about driving these commands unattended
belongs to the gh-stack skill — including that `--open` readies *existing*
pull requests too, so a stack deliberately holding a draft layer needs a
different sequence. Load that skill before running any `gh stack` command
rather than working from this summary.

From the web UI, create the child with its base set to the parent's branch and
choose **Create stack** to link them. Either way the result is what a base
pointer alone does not give you: a stack icon and a stack map in each pull
request's merge box, listing every layer with its status and letting a reviewer
move between them.

That map is the reason to bother. A reviewer opening a child sees a correct diff
either way, but only a real stack tells them where they are in the series and
how much of it is theirs to review.

**The body is still the commit message.** A squashed merge takes it verbatim, so
keep stack scaffolding out of it — the stack map already says what is stacked on
what, which is precisely why it should not also be prose in the body that ships
into `git log`. Write the body as the commit message it becomes, as if the
branch had never been stacked. Anything a reviewer needs about the stack itself
goes in a comment, which merging discards.

**When the base moves, re-run the child's full gate.** A clean base does not
vouch for the child — the child's tests run against code the base just changed,
and no command re-runs the gate for you.

Restack with `gh stack sync`, not by hand. It cascade-rebases every branch onto
its updated parent and pushes them atomically with `--force-with-lease`, where
rebasing and force-pushing "the child" is one-layer thinking: on A ← B ← C,
restacking B alone leaves C parented on B's superseded tip, so C's pull request
shows B's old commits inside its own diff and its reviewer reads changes that
are not theirs. Nothing errors — you find out when someone reviews the wrong
diff. Use `gh stack rebase` for the rebase without the push. Fix a finding on
the branch that owns the code, the parent's if the code is the parent's, and
reply on whichever pull request carries the thread.

**Merging is still mine, and stacks make that easier to get wrong.** A stack can
be merged in one click, all layers together — so it is exactly the button not to
press. Open the stack and hand over the URLs. When I merge a base on its own,
check that the child retargeted and is still mergeable rather than assuming
both.

Public preview means subject to change, and merge-queue support was still
rolling out when this was written. Check the behaviour you depend on rather than
trusting this paragraph to have aged well.

## Pull request reviews are local by default

When I ask to "review this PR" (or equivalent), review the checked-out pull
request yourself: resolve its exact head, inspect the local diff and the code it
depends on, and verify every finding. A generic review request does **not**
select or authorize a separate Codex or Claude reviewer.

**Local means where the reviewing happens, not where the findings land.** Post
them to GitHub on the lines they concern — a review summarized only in the
terminal is not a review anyone else can act on, and it leaves nothing to reply
to or resolve later.

**Reviews go up as `minjudd`, not as me.** GitHub will not let an author approve
their own pull request, so a review posted from my account can only ever be a
comment — the weaker thing, and silently so. Findings are submitted as one
review carrying a verdict: `REQUEST_CHANGES` when there are any, `APPROVE` when
the head is clean. `start-review-loop` owns those mechanics and the identity
preflight that goes with them. `start-fix-loop` owns the other half — verifying
a finding, fixing it, replying, and resolving the thread, in that skill's order.
Neither is repeated here, so there is one place to change when it changes.

Codex and Claude CLI reviews are opt-in. Run one only when I explicitly name it
("run a Codex review", "run a Claude review") — that explicit request is what
authorizes sending the repository context needed for the review to the named
service. Use the selected CLI directly; do not start a review with an
`@codex review` comment.

To run one: resolve the pull request head, run the selected CLI against that
exact code, and wait for the CLI process to finish before acting on its results.
CI going green is unrelated to review completion. Keep me updated about once a
minute during longer review runs.

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
