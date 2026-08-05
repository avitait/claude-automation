---
name: explain-diff
description: Teach the author what a branch/PR/diff does, in a Distill-style pedagogical walkthrough — four sections in strict order: **Background** (build the mental model *before* the change so the reader can even begin to understand it), **Intuition before details** (the goal + a worked example, no code yet), **Interactive figures** (small worked examples, Mermaid flowcharts / sequence / state diagrams, tables, or `try this` prompts — only where they earn their place), and **Literate code walk** (files in the order that tells the story, each preceded by a prose paragraph, not filesystem order). Use when the user asks to "explain this diff", "walk me through this branch", "teach me what this PR does", "help me understand what changed", "make sense of my diff", or similar. Not a review — no bug-hunting, no severity flags, no findings. Not for a human reviewer either — that is a different, "guided review" tool. This is for **the author (or someone learning the change) to build understanding**, and the deliverable is a chat message (with an optional durable save to a wiki / knowledge base).
---

# explain-diff

`git diff` is a bad teacher. It shows hunks in filesystem order, mixes essential change with formatting churn, and — worst — assumes you already know the system it lives in. This skill produces a **teaching** document about a diff: four sections that lead the reader *up to* the change, then *into* it. The output is a chat message aimed at the change's author (or a teammate learning the area), **not** a review artifact.

The pedagogical spine is fixed. Do not skip, reorder, or merge these sections:

1. **Background** — teach the system the change lives in, *before mentioning the change*.
2. **Intuition before details** — state the goal and give a worked example; no code yet.
3. **Interactive figures** — Mermaid diagrams (flowcharts, sequence, state), Markdown tables, or `try this` prompts, only where they add understanding.
4. **Literate code walk** — files in semantic order, each preceded by prose that says *what and why* before you show the code.

**What this is not.** Not a review. No bug-hunting, no severity labels (⭐/⚠️/P0/P1), no "this looks buggy", no suggestions to change the code. If you want bugs found, use a dedicated code-review skill. If you want a *reviewer* oriented on a PR, use a guided-review skill — it lives on the PR platform as a comment and is written for someone else. `explain-diff` is a chat deliverable for the person trying to *understand* the change.

## Inputs

- **Target resolution** (in order):
  1. Explicit PR number in the user's message → `gh pr view <N>` for metadata + `git fetch origin pull/<N>/head` for the head SHA.
  2. Explicit branch/ref (`explain the diff on origin/foo`) → resolve with `git rev-parse`; base is the repo's default branch (usually `origin/main` or `origin/master`) unless the user says otherwise.
  3. Otherwise → **current branch vs the default branch**: `git diff $(git merge-base origin/main HEAD)...HEAD`, plus uncommitted changes (`git diff HEAD`) if any. Say "including uncommitted work" in the opening line when uncommitted is included.
- **`gh` is authenticated** for the repo you're working in.
- **Repo context you can pull in**: any high-level architecture doc the repo has (e.g. `docs/ARCHITECTURE.md`, root `README.md`, a top-level `CLAUDE.md`), and any per-package/service `CLAUDE.md` or `README.md` for the areas the diff touches. If the repo has none of these, the Background section relies entirely on the code you read.
- **Ticket grounding** (optional): if the PR title or body references an issue tracker key (Jira, Linear, GitHub issues, etc.), fetch it via whatever MCP / API integration is available to ground the *goal* in stated intent. Silent skip if unavailable — infer from PR body + diff.

## Steps

### 0. Resolve the target and load context

Resolve per the order above. For a PR:

```
gh pr view <N> --json number,title,body,author,baseRefName,headRefName,headRefOid,additions,deletions,files
git fetch origin pull/<N>/head
```

Address files by SHA (`git show <headRefOid>:<path>`), not `FETCH_HEAD` (any later fetch clobbers it) and never `gh pr checkout` (mutates the worktree).

Then read any repo-level architecture docs and the per-package docs of every area the diff touches. **You cannot write a good Background section without them.** The Background isn't reciting these docs — it's synthesizing them into just the concepts the reader needs to understand *this* change.

### 1. Read the diff FULLY, then classify + order

Read the whole diff, not just hunks. For each changed file also read its surroundings — callers of changed functions, base classes, sibling tests, the module docstring — enough to understand *why* the file changed and how it fits. Then classify each file by semantic role:

| Role | What goes here | In the walk |
|---|---|---|
| **Core** | the substantive logic — where the goal is actually realized | walked in full, first, in Plan order |
| **Consequence / ripple** | call sites, wiring, signature/import updates, config that exists *because of* Core | walked after Core, framed as "Core forced this" |
| **Auxiliary / noise** | test files (unit, e2e, fixtures, snapshots), formatting, pure renames, lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock`, `Gemfile.lock`, `go.sum`, etc.), generated code, autogenerated model/schema output | one collapsed list at the end, not walked |

A file is only **Core** if reading it is how you *first* understand the change. When unsure between Core and Consequence, ask: would the reader start here, or only arrive here after the Core? Start-here → Core.

From this, derive the **Plan** — the ordered logical steps the author took ("introduce X → route existing callers through it → backfill via migration → wire the new UI branch"). The Plan is the spine of the code walk.

### 2. Section 1 — Background (build the mental model first)

**The reader does not yet know what changed. Do not mention it.** Not in the opening line, not implicitly.

**Reader persona.** Assume the reader has worked in this repo for a while but has shallow knowledge of most subsystems. Assume they know the languages and major frameworks in use (Python, JavaScript/TypeScript, React/Vue, SQL, whatever the repo runs on) — but do **not** assume they know how any specific subsystem works internally, what contracts exist between packages, or why architectural conventions exist. When the diff touches a subsystem, **briefly teach that subsystem's role and shape**, even if it's documented elsewhere in the repo. **Prefer explaining one time too many over one time too few.**

Cover, in this order:

- **The subsystem's role and shape.** One short paragraph per subsystem the diff touches: what is this thing, what does it own, what talks to it, what does it hand out. Don't recite the whole architecture doc; give the reader enough of a mental model to make sense of the walk. If two subsystems are touched, one paragraph each.
- **The prior state of the thing being modified.** What shape was `X` before this PR touched it? What contract did it hold? The whole rest of the walkthrough is a *delta* — Background is where you name what the delta is against.
- **Load-bearing epic / stacking context.** If this PR is part of a larger multi-PR body of work, or stacked on a non-default base branch, name it — the reader can't infer that from the diff alone.
- **A specific gotcha the diff turns on.** Non-obvious conventions or asymmetries the reader would trip over. Example: "app-A inlines its login form; app-B extracts it as a shared component" — that only matters because the same conceptual edit lands differently in the two apps.

**Close with a `### Concepts you'll meet` glossary.** After the paragraphs above, end Background with a subheading `### Concepts you'll meet` followed by 3–5 bullet points of the form `**term** — one-sentence definition.`. Pick terms that (a) appear in Intuition or Code walk *and* (b) are load-bearing but plausibly new-to-the-reader given the persona — an acronym you're about to use (TOTP, JWT refresh window, CIDR block), a repo-invented term (whatever the codebase calls its domain objects), a specific token or DTO the walk keeps referring to, an obscure library primitive. Skip anything the persona already owns (component, store, `async def`, HTTP status). This box is the reader's **compounding personal glossary** of the codebase across `explain-diff` runs, so err on including a term the reader "should know" over dropping one they don't. Definitions are one sentence each, not paragraphs.

**Length target: 3–5 short paragraphs, plus the glossary.** Skew longer on the paragraphs, not shorter — under-explaining a subsystem the reader hasn't opened in six months is worse than a paragraph they can skim past.

**Anti-patterns to avoid.**
- Starting with "This PR adds…", "The change introduces…", or any variant. If the reader takes away *what* changed from Background, you've written it wrong.
- Skipping subsystem shape because "it's in the docs already". The reader has a year in the repo, not a year in *this subsystem*; teach it anyway. Err over-explaining.
- Re-teaching the language / framework itself (that components have props, that Python has decorators, that HTTP has status codes). Those are the "basics" the persona owns; the *subsystem* is not.
- Reciting the whole architecture doc. Teach only the subsystems this diff touches — but teach those properly.
- A wall of concept cards *in the paragraphs*. Background prose should have a spine — usually the prior state of the specific thing this PR is about to modify — not a definition list. Definitions go in the "Concepts you'll meet" glossary at the end, one sentence each; the paragraphs above narrate.
- Skipping the "Concepts you'll meet" glossary because "those terms come up in the walk anyway". The glossary is the reader's *compounding artifact* across many `explain-diff` runs — its value is in being harvestable into a personal codebase glossary, not in being non-redundant with the prose. Always include it.
- Making the glossary definitions long. One sentence, tops. If it wants to be a paragraph, the term belongs in the Background prose or the Code walk, not the glossary.

### 3. Section 2 — Intuition before details (goal + worked example, no code)

Now — and only now — say what the change *does*. This is the well-written-commit-message part, followed by a concrete feel for the essence.

Structure:

- **Goal** — 1–2 sentences. The problem solved / outcome intended, grounded in the ticket + code. Not a restatement of the PR title.
- **The essence** — one paragraph explaining *how* the change achieves the goal, at the level of ideas, not code. "It moves the check from post-scan to pre-scan, so cached results skip the expensive step entirely." No file names, no function names — those come in Section 4.
- **A worked example** — pick one small concrete scenario and trace it through the *behavior*, before and after. Example: *"Before: an event with 12 duplicate identifiers ran the enrichment step 12 times. After: it runs once and the other 11 hit the per-request cache."* Use obviously-fake but concrete values (`fakeuser1`, `host-1`, `1.2.3.4`) — never real customer data.

No code blocks in this section. Prose only. Length: half a page tops. If the goal is genuinely hard to state in two sentences, that's a signal the diff is doing more than one thing — say so plainly ("this PR bundles two related changes: X, and the follow-on Y that X enables"), and give each its own goal + essence + example.

**Close Intuition with a comprehension anchor.** After the worked example, end Section 2 with a single sentence bolded lead-in of the form **"If you remember one thing:"** followed by the load-bearing fact — the *one thing* about this change that, if the reader retained nothing else, would still let them reason about future work in this area. One sentence, not two. Pedagogy research on one-line takeaways is unambiguous: retention roughly doubles when a "so-what" summary immediately follows an explanation. This is cheap and it's what actually sticks.

**Anti-patterns to avoid.**
- Skipping the "If you remember one thing" anchor. It costs one sentence, and it's the single highest-leverage element in the whole document for retention. Always include it.
- Making the anchor two sentences. If you have two things, pick the one — the picking *is* the exercise; failing at it means Intuition is fuzzy above.
- An anchor that restates the section heading ("If you remember one thing: this PR is about MFA"). The anchor names the *load-bearing fact*, not the topic.

### 4. Section 3 — Interactive figures (only where they earn their place)

Interactivity is a crutch when overused. Every figure must **provide understanding that prose can't**. If none does, this section is one line: "*Nothing here that a static explanation didn't already cover.*" That is a valid outcome — do not fabricate figures to fill the section.

Kinds of figures that earn their place:

- **Mermaid diagram.** Flowchart, sequence, or state diagram in a ```` ```mermaid ```` fenced block. Notion (April 2024+) renders these as real graphics; GitHub renders them in PR descriptions and issue comments but *not* PR review comments; most chat clients (Claude Code, terminals) show the raw source. Use when the topology or control flow *is* what changed — a state machine for a new status enum, a sequence diagram for a multi-hop protocol handshake, a flowchart with subgraphs for a before/after comparison. Prefer `sequenceDiagram` for a traced worked example, `stateDiagram-v2` for a status/enum lifecycle, `flowchart TD` (with `subgraph` for before/after) for control flow. Keep it small — 6–10 nodes; a 30-node Mermaid graph is unreadable in every renderer. **Portability tradeoff:** the durable-copy render surface (Notion, Confluence, a Markdown wiki with Mermaid support) is where the diagram becomes a graphic; chat readers see raw Mermaid source. That's the deliberate call — the wiki is where the walkthrough lives after chat scrolls.
- **Markdown table.** Two-to-four columns of concrete inputs → concrete outputs, showing the delta. Useful for state-through-time, request/response before/after, enum-value mappings. Renders identically in chat, wikis, and Git-hosted READMEs — no portability tradeoff.
- **Traced example.** Take one concrete input from Section 2's worked example and step through the *new* code — "at line 47 we compute `x=…`, so the branch at line 52 goes right, so we call `foo(…)` with…". This is essentially execution-by-hand; use when the change's correctness depends on control flow that's hard to eyeball. Often pairs well with a `sequenceDiagram` above it.
- **`try this` prompt.** A specific local command the reader can run to see the change work — a dev-server command and then trigger the scenario, a DB query that shows the new column, a unit test to run. Only if it's genuinely reproducible on the reader's machine with no exotic setup; skip otherwise.
- **`AskUserQuestion`** — offer 2–4 concrete scenarios and ask which one the reader wants traced. Use rarely, only when the change has genuinely different regimes (e.g. "cached hit", "cache miss with prior state", "cache miss cold") and the reader picking one is more useful than tracing all three.

Each figure gets a one-line caption saying *what it shows and why it matters*. No figure without a caption. Two well-chosen figures beat five decorative ones.

**Anti-patterns to avoid.**
- Adding a diagram because the section is "supposed to have" one.
- Mermaid graph that restates the file structure — the reader will see it in Section 4.
- Mermaid diagrams with more than ~10 nodes. If the graph needs 20 boxes to explain, the change is doing too much for one figure to hold — split the figure or drop it.
- ASCII box-drawing (`─│┌┐└┘▶◀`) instead of Mermaid. Mermaid is the modern convention; if you find yourself reaching for `─│`, stop and write a `flowchart TD` block instead.
- A `try this` command that requires setting up a new fixture the reader doesn't have.

### 5. Section 4 — Literate code walk (semantic order + prose per file)

Now show the code. Files in **Plan order** (from step 1), not filesystem order. Structure:

- One heading per file — `#### Core · path/to/file.py` (or `Consequence`).
- Before the code, **one prose paragraph** that says: *what this file does now, what part of the Plan it realizes, and — if non-obvious — why it's shaped this way rather than an alternative.* The paragraph must earn the code that follows; if you can't write it, you don't understand the file well enough yet — go back to step 1.
- Then the **key lines**, quoted verbatim in a fenced block with the language tag. Not the whole file, not a fat range — the lines that carry the point. If a file has two distant meaningful ranges, show them as two blocks with a one-line prose bridge between.
- If a line is subtle, add a `#` / `//` gloss right after the quote (outside the fenced block, prose) explaining *why* it's written that way. Not what it does — the code says what.

Order within Core follows the Plan, not alphabet. Consequences come after Core, framed as `#### Consequence · path/… — [what forced this from Core]`. Test files are not walked — they go straight into the Auxiliary collapsed block below.

Auxiliary at the end, one collapsed block:

```
<details><summary>Auxiliary (K files) — skim</summary>

- `tests/test_foo.py` — coverage for the new branch
- `package-lock.json` / `uv.lock` — regeneration, no manual edits
- `packages/models/**` — autogenerated schema output
- `bar.py` — formatter-only changes
</details>
```

Keep prose tight — the code carries the content, not the prose. One paragraph per file, not three. If a file needs three paragraphs, split it into two Core chapters at the meaningful boundary and give each its own prose.

**Anti-patterns to avoid.**
- Filesystem-order walk — the whole point is to reorder into the story.
- Pasting whole files. A 200-line quote is as skimmable as the raw diff.
- Prose that echoes the code (`this function calls foo`) — the reader can see that. Prose says *why*.
- Introducing a concept in Section 4 that Background didn't prepare the reader for. If it comes up here, it was missing from Section 1 — go back and add it.

### 6. Deliver

The primary deliverable is a **chat message** printed in full. Optionally, save the same body to a durable knowledge base (Notion, Confluence, a Markdown wiki, a `docs/` folder in the repo) so the walkthrough survives after the chat scrolls. If you configure a durable save target (see below), do it every run.

**Body structure (identical for chat and any durable save).** Open with a one-line frame that names the target and mode:

- **PR mode** — the PR number + title as a **clickable link to the PR** (Markdown: `[**PR #<N> · <PR title>**](<PR URL>)`), then a `— walked at <short-SHA>` tail, plus `stacked on <base-ref>` if the base ref isn't the default branch. The link at the top is non-negotiable — it's the reader's escape hatch back to the source of truth.
- **Local mode** — branch name + short SHA (no link; there's no PR to point at). Include "including uncommitted work" if any.

Then the four sections, in order, with clear headings (`## Background`, `## Intuition`, `## Interactive figures`, `## Code walk`). Close with a two-line footer:

```
---
*explain-diff · <target-descriptor> · <short-SHA>*
```

Nothing else. No summary, no "hope this helps", no next-step suggestions.

**Durable save target (optional but recommended).** Configure this once for your team and reuse. Options:

- **Notion** — with the Notion MCP tool, create a page under a hardcoded parent page (title = the PR title verbatim; icon = `📖`). Do not search for the parent each run — put its ID in your team's `CLAUDE.md` and reuse.
- **Confluence** — create a page under a chosen space with the same title convention.
- **A repo `docs/` folder** — write a Markdown file at `docs/reviews/<PR-number>-<slug>.md` and commit it.
- **None** — chat-only delivery is a fine default.

Regardless of the save target: **never print customer / client data** in the title or body (see general safety rules for your team). If a target save fails, still print the walkthrough — say plainly "*Durable save failed: <one-line reason>*" in chat and continue.

**Chat.** Print the full walkthrough. If a durable save succeeded, end with a single line: `📖 Also saved: <URL or path>`.

**Re-run** (there's already a saved page for this target): create a fresh one anyway — durable stores are cheap, and diffs shift. The title's short SHA disambiguates.

## Edge cases

- **Huge diff** (> ~40 files): Background and Intuition are unchanged in length — they don't grow with file count. The code walk collapses aggressively: group Consequences by subsystem into single chapters rather than per-file; keep Auxiliary as one `<details>`.
- **Docs-only / lockfile-only PR**: degenerate. Background is one paragraph, Intuition is one sentence ("this bumps dependency X because Y"), no Interactive figures, and the code walk is a single collapsed block. Say the diff is degenerate so the reader isn't confused by the short output.
- **Frontend PR**: whatever framework the repo uses (React, Vue, Svelte, Angular) — its primitives are what the persona owns. Treat autogenerated model/schema/type output as Auxiliary.
- **Migration PR**: Background must explain the *table's* role, not just the migration tool's mechanics; Intuition names the data change (adds column X for reason Y). The migration file goes in the code walk; the ORM/schema updates are Consequences.
- **Uncommitted changes only** (nothing committed vs the default branch): still works — target descriptor becomes `working tree vs origin/main`, footer SHA is the local `HEAD` short SHA with `+uncommitted`.
- **Diff spans an unrelated cleanup**: name it in Intuition ("this PR does one thing plus an unrelated formatting sweep — I'll cover the primary change; the sweep is in Auxiliary") and put the cleanup files in Auxiliary. Don't try to weave a narrative that pretends they're related.

## Things to avoid

- **Reviewing.** No ⭐/⚠️, no P0/P1, no "this looks wrong", no fix suggestions. If you spot something suspicious, note it neutrally *once* in the relevant walk paragraph ("this only handles the non-null case — verify that's intended") and move on. If the user wants bugs found, redirect to a code-review skill.
- **Mentioning the change in Background.** The entire pedagogical trick is that the reader is oriented *before* they know what's coming. Violating this collapses the skill into a badly-formatted guided review.
- **Fabricating interactive figures.** Better to write "*Nothing here that a static explanation didn't already cover.*" than to add a diagram that decorates rather than teaches.
- **Filesystem order in the code walk.** Semantic order is non-negotiable — it's the whole point of the "literate" framing.
- **Skipping the per-file prose paragraph.** Without it, Section 4 is just a colored `git diff` — you've defeated the point.
- **Prose that echoes the code.** "`x = foo()` — this assigns the return of `foo` to `x`" is worse than nothing. Prose is for *why*, code is for *what*.
- **Padding.** Every paragraph must be one the reader would miss if you removed it. If a paragraph could be deleted with no loss to understanding, delete it.
- **Printing customer / client data** — never reprint real user names, hostnames, IPs, tokens, or company names, even if they appear in the diff. Use fake-obvious values.
- **Posting the output to the PR platform** (as a PR comment or PR description). Delivery is chat + optional durable save only. If the user wants a PR comment or a walkthrough for someone else to review from, that's a guided-review skill — say so.
- **Searching the durable store for the parent page** each run. Hardcode the parent ID / path once at setup. Do not call `search` for it every time.
- **`gh pr checkout`** — use `git fetch origin pull/<N>/head` and address by `headRefOid`.
- **Reading only hunks.** You cannot write good Background or good per-file prose without reading the surrounding code — this is step 1's mandatory `git show <sha>:<path>` reads.
