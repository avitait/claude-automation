---
name: explain-topic
description: >-
  Teach the user a codebase topic (a subsystem, concept, workflow, protocol, or feature) in a Distill-style pedagogical walkthrough — four sections in strict order: **Intro to the topic** (name what it is, where it lives, what problem it solves, what its contracts are, close with a "Concepts you'll meet" glossary), **Intuition before details** (the goal + a worked example, no code yet), **Interactive figures** (architecture, sequence, and state diagrams, tables, or `try this` prompts — topics usually warrant more figures than diffs, so this section pulls more weight), and **Literate code walk** (files in the order that tells the story, each preceded by a prose paragraph, not filesystem order). Use when the user asks to "explain how X works", "walk me through the Y subsystem", "teach me the Z pipeline", "help me understand [feature]", or similar. Not a review — no bug-hunting, no severity flags, no findings. Not tied to a diff — that is a separate "explain diff" skill. This is for **someone trying to build a mental model of an existing part of the codebase**, and the deliverable is a chat message (with an optional durable save to a wiki / knowledge base).
---

# explain-topic

`git grep` and file trees are bad teachers. They surface names in alphabetical order, mix load-bearing modules with test scaffolding, and — worst — assume you already know what you're looking at. This skill produces a **teaching** document about a topic in the codebase: four sections that land the reader inside the topic, then walk them through it. The output is a chat message aimed at someone building a mental model of an existing subsystem, concept, or workflow — **not** a review artifact, and **not** tied to a specific diff.

The pedagogical spine is fixed. Do not skip, reorder, or merge these sections:

1. **Intro to the topic** — name what it is, where it lives, what problem it solves, and what contracts it has with the outside.
2. **Intuition before details** — state the goal and give a worked example; no code yet.
3. **Interactive figures** — Mermaid diagrams (architecture, sequence, state), Markdown tables, or `try this` prompts. Topics warrant more figures than diffs — this section carries real weight here.
4. **Literate code walk** — files in semantic order, each preceded by prose that says *what and why* before you show the code.

**What this is not.** Not a review. No bug-hunting, no severity labels (⭐/⚠️/P0/P1), no "this looks buggy", no suggestions to change the code. If you want bugs found, use a dedicated code-review skill. If you want a walkthrough of a specific *diff*, use an `explain-diff` skill. If you want a *reviewer* oriented on a PR, use a guided-review skill. `explain-topic` is a chat deliverable for the person trying to *understand an existing part of the codebase*.

## Inputs

- **Topic resolution** — free-form phrase in the user's message (`explain how the auth flow works`, `walk me through the event pipeline`, `teach me the reporting system`). No PR / branch / ref resolution — the "target" is a concept, not a diff.
- **Repo context you must pull in**: any high-level architecture doc the repo has (e.g. `docs/ARCHITECTURE.md`, root `README.md`, a top-level `CLAUDE.md`), and any per-package/service `CLAUDE.md` or `README.md` for the areas the topic touches. **You cannot write a good Intro without them.** If the repo has none, the Intro rests entirely on the code you read.
- **Codebase exploration** is the substitute for `gh pr view`. Use an `Explore`-style subagent (or `grep`/`find` yourself if the repo is small) to locate the load-bearing files (entry points, main logic modules, data models, and — as context, not walked — tests).

## Steps

### 0. Resolve the topic and load context

The user's topic phrase is your query. Launch an exploration subagent with a topic-focused prompt: find entry points, main logic modules, data models (ORM + DTOs), consumers, and tests. Ask for file paths + one-line role descriptions, not code excerpts.

Then read, by path:

- The files exploration flagged as load-bearing (not just hunks — whole files where feasible).
- Any repo-level architecture / conventions doc.
- The per-package/service doc of every area the topic touches.

The Intro isn't reciting these docs — it's synthesizing them into just the concepts the reader needs to understand *this* topic.

### 1. Read the code FULLY, then classify + order

Read the whole surface, not just the entry point. For each load-bearing file also read its surroundings — callers, base classes, sibling tests, the module docstring — enough to understand how the topic *actually works*, not just its shape. Then classify each file by role:

| Role | What goes here | In the walk |
|---|---|---|
| **Core** | files that *define* the topic — entry points, main logic, data models, the algorithms that realize the topic's job | walked in full, first, in Plan order |
| **Supporting** | files that surround the topic — callers, config, small utilities, contract-adjacent DTOs | walked after Core, framed as "this is how Core connects to the rest of the system" |
| **Auxiliary / noise** | tests (unit, e2e, fixtures, snapshots), generated code (schema/model output), lockfiles, historical migrations that predate the current shape | one collapsed list at the end, not walked |

A file is only **Core** if reading it is how you *first* understand the topic. When unsure between Core and Supporting, ask: would the reader start here, or only arrive here after grasping the Core? Start-here → Core.

From this, derive the **Plan** — the ordered logical steps a reader would take to understand the topic ("data model → producer → consumer → lifecycle → error paths", or "public API entrypoint → dispatch → handler → side effects"). The Plan is the spine of the code walk; it is *not* the order the code was authored in or the alphabetical order of paths.

**Broad-topic checkpoint.** If exploration surfaces more than ~15 Core+Supporting files, stop and use `AskUserQuestion` to confirm scope with the user: "I found A, B, C, D as the load-bearing pieces — walk all of these, or narrow to X?" Don't guess the reader's real interest.

### 2. Section 1 — Intro to the topic (build the mental model)

**Reader persona.** Assume the reader has worked in this repo for a while but has shallow knowledge of most subsystems. Assume they know the languages and major frameworks in use — but do **not** assume they know how any specific subsystem works internally, what contracts exist between packages, or why architectural conventions exist. When the topic touches a subsystem, **briefly teach that subsystem's role and shape**, even if it's documented elsewhere in the repo. **Prefer explaining one time too many over one time too few.**

Cover, in this order:

- **What this topic is** — one paragraph. The role it plays in the product. Give the reader the one-sentence mental sticker they can carry to the rest of the doc. Do not enumerate files. Do not name functions.
- **Where it lives** — one paragraph. The package(s) that own it and the shape of ownership. E.g. "the algorithm lives in `services/dedup/`; the fingerprint contract it consumes is defined in `shared/observables.py`; the migration that added the dedup key column is in `migrations/versions/`." Package-level, not file-level — the file names come in Section 4.
- **The problem it solves** — one paragraph. Why does this exist? What was painful before, or what would break without it? Ground this in product behavior the reader can feel, not architectural aesthetics.
- **Contracts with the outside** — one paragraph. What the topic consumes (event types, DTOs, DB rows, upstream tasks) and what it produces (side effects, new rows, emitted jobs, HTTP responses). If the topic sits between two subsystems, name each boundary explicitly.
- **A specific gotcha** — one paragraph. A non-obvious asymmetry, convention, or invariant the reader would trip over. Example: "The dedup key is computed from the *canonical* fingerprint, not the raw one — two events with different casing collide on purpose." Only include if there's a real gotcha; skip if not.

**Close with a `### Concepts you'll meet` glossary.** After the paragraphs above, end the Intro with a subheading `### Concepts you'll meet` followed by 3–5 bullet points of the form `**term** — one-sentence definition.`. Pick terms that (a) appear in Intuition or Code walk *and* (b) are load-bearing but plausibly new-to-the-reader given the persona — an acronym you're about to use (TOTP, JWT refresh window, CIDR block), a repo-invented term (whatever the codebase calls its domain objects), a specific token or DTO the walk keeps referring to, an obscure library primitive. Skip anything the persona already owns (component, store, `async def`, HTTP status). This box is the reader's **compounding personal glossary** of the codebase across `explain-topic` and `explain-diff` runs, so err on including a term the reader "should know" over dropping one they don't. Definitions are one sentence each, not paragraphs.

**Length target: 4–6 short paragraphs, plus the glossary.** Slightly longer than `explain-diff`'s Background — there is no delta to anchor on, so the Intro carries more of the mental-model load.

**Anti-patterns to avoid.**
- Naming specific files or functions in the Intro. Those come in Section 4. The Intro teaches the *shape* of the topic, not its file inventory.
- Reciting the whole subsystem doc. Synthesize; don't quote.
- Re-teaching the language / framework itself (that components have props, that Python has decorators, that HTTP has status codes). Those are the "basics" the persona owns; the *subsystem* is not.
- A wall of concept cards *in the paragraphs*. Intro prose should have a spine — usually starting from "what this topic is for" and expanding outward — not a definition list. Definitions go in the "Concepts you'll meet" glossary at the end, one sentence each; the paragraphs above narrate.
- Skipping the "Concepts you'll meet" glossary because "those terms come up in the walk anyway". The glossary is the reader's *compounding artifact* across many `explain-topic` and `explain-diff` runs — its value is in being harvestable into a personal codebase glossary, not in being non-redundant with the prose. Always include it.
- Making the glossary definitions long. One sentence, tops. If it wants to be a paragraph, the term belongs in the Intro prose or the Code walk, not the glossary.

### 3. Section 2 — Intuition before details (goal + worked example, no code)

Now — and only now — say what the topic *does* at the level of ideas. This is the "what would you tell a new hire in the hallway" part, followed by a concrete feel for the essence.

Structure:

- **Goal** — 1–2 sentences. What the topic accomplishes for the product. Not a restatement of the section heading. Ground it in outcome (why does the user or system care that this exists).
- **The essence** — one paragraph explaining *how* the topic achieves the goal, at the level of ideas, not code. "It groups incoming events by a normalized fingerprint hash and keeps the earliest in each group; downstream systems only see one representative per fingerprint." No file names, no function names — those come in Section 4.
- **A worked example** — pick one small concrete scenario and trace it through the *behavior*. Example: *"Three events arrive within an hour, all for the same user pivoting between two hosts. All three normalize to the same fingerprint. Event #1 is kept as the group leader; events #2 and #3 are attached as group members and never emit their own downstream signal."* Use obviously-fake but concrete values (`fakeuser1`, `host-1`, `1.2.3.4`) — never real customer data.

No code blocks in this section. Prose only. Length: half a page tops. If the topic is genuinely hard to state in two sentences, that's a signal the scope is too broad — go back to the broad-topic checkpoint in step 1 and narrow with the user, or name the split explicitly ("this topic really has two intertwined halves: X, and the follow-on Y that X enables"), and give each its own goal + essence + example.

**Close Intuition with a comprehension anchor.** After the worked example, end Section 2 with a single sentence bolded lead-in of the form **"If you remember one thing:"** followed by the load-bearing fact — the *one thing* about this topic that, if the reader retained nothing else, would still let them reason about future work in this area. One sentence, not two. Pedagogy research on one-line takeaways is unambiguous: retention roughly doubles when a "so-what" summary immediately follows an explanation. This is cheap and it's what actually sticks.

**Anti-patterns to avoid.**
- Skipping the "If you remember one thing" anchor. It costs one sentence, and it's the single highest-leverage element in the whole document for retention. Always include it.
- Making the anchor two sentences. If you have two things, pick the one — the picking *is* the exercise; failing at it means Intuition is fuzzy above.
- An anchor that restates the section heading ("If you remember one thing: this topic is about dedup"). The anchor names the *load-bearing fact*, not the topic.

### 4. Section 3 — Interactive figures (topics warrant more of them)

Interactivity is a crutch when overused. Every figure must **provide understanding that prose can't**. If none does, this section is one line: "*Nothing here that a static explanation didn't already cover.*" That is a valid outcome — do not fabricate figures to fill the section.

That said, topics almost always have multiple parts (data flow, lifecycle, external contracts, regime branches), so **the expectation is higher here than in `explain-diff`**. Most topic walkthroughs earn 2–4 figures where a diff walkthrough often earns 1–2. Reach for combinations, not a single mega-diagram.

Kinds of figures that earn their place:

- **Architecture diagram** (`flowchart TD` with `subgraph`s per package). Data flow across the packages that own the topic — producer → transport → consumer → side effect. This is the figure most often *missing* from topic walkthroughs, and it's usually the one that pays off most. Keep it small — 6–10 nodes; a 30-node graph is unreadable in every renderer.
- **Sequence diagram** (`sequenceDiagram`). Request/response, or async producer/consumer with a queue in the middle. Use when the topic has time-ordered interactions between multiple actors.
- **State diagram** (`stateDiagram-v2`). Lifecycle if the topic has statuses or phases (an enum whose transitions carry meaning — e.g. a task lifecycle, a token's active/refreshing/expired states, an order state machine).
- **Markdown table.** Two-to-four columns of concrete inputs → concrete outputs, or enum-value → meaning, or contract-in → contract-out. Renders identically in chat, wikis, and Git-hosted READMEs.
- **Traced example.** Take the concrete input from Section 2's worked example and step through the *actual code paths* — "at line 47 we compute `x=…`, so the branch at line 52 goes right, so we call `foo(…)` with…". This is execution-by-hand; pair with a `sequenceDiagram` above it when the flow spans multiple actors.
- **`try this` prompt.** A specific local command that exercises the topic — a dev-server command and then trigger the scenario, a DB query that shows the state, a unit test to run. Only if it's genuinely reproducible on the reader's machine with no exotic setup; skip otherwise.
- **`AskUserQuestion` for regime choice.** Offer 2–4 concrete regimes and ask which one the reader wants traced. Use when the topic has genuinely distinct paths (cached hit / cache miss cold / cache miss with prior state) and the reader picking one is more useful than tracing all three.

**Portability tradeoff.** Notion (April 2024+) renders Mermaid as real graphics; GitHub renders it in PR descriptions and issue comments but *not* PR review comments; most chat clients show the raw Mermaid source. Since `explain-topic`'s deliverable is chat + optional durable save (no live PR platform), the durable-save surface is where the diagram becomes a graphic. That's the deliberate call — the wiki is where the walkthrough lives after chat scrolls.

Each figure gets a one-line caption saying *what it shows and why it matters*. No figure without a caption. Two well-chosen figures beat five decorative ones.

**Anti-patterns to avoid.**
- Adding a diagram because the section is "supposed to have" one.
- **A mega-diagram of the whole subsystem.** If the graph needs 20 boxes to explain, split it into two focused figures (e.g. "data flow" + "lifecycle") or drop the sprawling one entirely. Readers can't hold 30 nodes; two 8-node figures beat one 30-node figure every time.
- Mermaid graph that restates the file structure — the reader will see it in Section 4.
- ASCII box-drawing (`─│┌┐└┘▶◀`) instead of Mermaid. Mermaid is the modern convention; if you find yourself reaching for `─│`, stop and write a `flowchart TD` block instead.
- A `try this` command that requires setting up a new fixture the reader doesn't have.

### 5. Section 4 — Literate code walk (semantic order + prose per file)

Now show the code. Files in **Plan order** (from step 1), not filesystem order. Structure:

- One heading per file — `#### Core · path/to/file.py` (or `Supporting`).
- Before the code, **one prose paragraph** that says: *what this file does, what part of the Plan it realizes, and — if non-obvious — why it's shaped this way rather than an alternative.* The paragraph must earn the code that follows; if you can't write it, you don't understand the file well enough yet — go back to step 1.
- Then the **key lines**, quoted verbatim in a fenced block with the language tag. Not the whole file, not a fat range — the lines that carry the point. If a file has two distant meaningful ranges, show them as two blocks with a one-line prose bridge between.
- If a line is subtle, add a `#` / `//` gloss right after the quote (outside the fenced block, prose) explaining *why* it's written that way. Not what it does — the code says what.

Order within Core follows the Plan, not alphabet. Supporting comes after Core, framed as `#### Supporting · path/… — [what it provides to Core]`. Test files are not walked — they go straight into the Auxiliary collapsed block below.

Auxiliary at the end, one collapsed block:

```
<details><summary>Auxiliary (K files) — skim</summary>

- `tests/test_dedup.py` — coverage for the main paths
- `packages/models/**` — autogenerated schema output
- `migrations/versions/2024xxxx_add_dedup_key.py` — added the DB column that Core reads
</details>
```

Keep prose tight — the code carries the content, not the prose. One paragraph per file, not three. If a file needs three paragraphs, split it into two Core chapters at the meaningful boundary and give each its own prose.

**Anti-patterns to avoid.**
- Filesystem-order walk — the whole point is to reorder into the story.
- Pasting whole files. A 200-line quote is as skimmable as `git grep`.
- Prose that echoes the code (`this function calls foo`) — the reader can see that. Prose says *why*.
- Introducing a concept in Section 4 that the Intro didn't prepare the reader for. If it comes up here, it was missing from Section 1 — go back and add it (either to the paragraphs or the glossary).

### 6. Deliver

The primary deliverable is a **chat message** printed in full. Optionally, save the same body to a durable knowledge base (Notion, Confluence, a Markdown wiki, a `docs/` folder in the repo) so the walkthrough survives after the chat scrolls. If you configure a durable save target (see below), do it every run.

**Body structure (identical for chat and any durable save).** Open with a one-line frame that names the topic:

```
**Topic: <topic phrase>** — walked at <short-SHA of HEAD>
```

Then the four sections, in order, with clear headings (`## Intro`, `## Intuition`, `## Interactive figures`, `## Code walk`). Close with a two-line footer:

```
---
*explain-topic · <topic phrase> · <short-SHA>*
```

Nothing else. No summary, no "hope this helps", no next-step suggestions.

**Durable save target (optional but recommended).** Configure this once for your team and reuse. Options:

- **Notion** — with the Notion MCP tool, create a page under a hardcoded parent page (title = the topic phrase in sentence case; icon = `📚`). Do not search for the parent each run — put its ID in your team's `CLAUDE.md` and reuse.
- **Confluence** — create a page under a chosen space with the same title convention.
- **A repo `docs/` folder** — write a Markdown file at `docs/topics/<slug>.md` and commit it.
- **None** — chat-only delivery is a fine default.

Regardless of the save target: **never print customer / client data** in the title or body. If a target save fails, still print the walkthrough — say plainly "*Durable save failed: <one-line reason>*" in chat and continue.

**Chat.** Print the full walkthrough. If a durable save succeeded, end with a single line: `📚 Also saved: <URL or path>`.

**Re-run** (there's already a saved page for this topic): create a fresh one anyway — durable stores are cheap, and codebases shift. The title's short SHA disambiguates via the frame line.

## Edge cases

- **Broad topic** — if step 1 surfaces more than ~15 load-bearing files, `AskUserQuestion` to confirm scope with the user before writing. Better to narrow up front than to produce a 40-page doc no one reads.
- **Cross-package topic** — Intro's "Where it lives" paragraph covers each package's role in one sentence; Code walk groups by package (backend → frontend within each phase of the Plan, never reverse).
- **Frontend-only topic** — whatever framework the repo uses (React, Vue, Svelte, Angular) — its primitives are what the persona owns and don't need re-teaching.
- **Migration/data-model topic** — Intro must explain the *table's* role and lifecycle, not just ORM mechanics; Intuition names the shape of data the table holds and the invariants it enforces; the migration files go in Auxiliary (they're historical), the ORM + query sites are Core.
- **Topic spans backend + frontend + migration** — Intro explains the contract at each boundary; Code walk order goes data model → backend → frontend, never reverse.
- **Extremely narrow topic** (a single utility function, a single enum) — degenerate. Intro is one paragraph, Intuition is one sentence + a two-line example, Interactive figures is likely "*Nothing here that a static explanation didn't already cover.*", Code walk is one Core chapter. Say the topic is narrow so the reader isn't confused by the short output.

## Things to avoid

- **Reviewing.** No ⭐/⚠️, no P0/P1, no "this looks wrong", no fix suggestions. If you spot something suspicious, note it neutrally *once* in the relevant walk paragraph ("this only handles the non-null case — verify that's intended") and move on. If the user wants bugs found, redirect to a code-review skill.
- **Naming individual files/functions in the Intro.** Section 1 teaches the *shape* of the topic — package-level, contract-level. The file tree comes in Section 4. Violating this collapses the skill into a badly-formatted `git grep` narration.
- **Fabricating topic scope broader than the user asked.** If the user says "explain the fingerprint hash function", don't expand into "the entire event pipeline". Confirm scope via `AskUserQuestion` before expanding.
- **Fabricating interactive figures.** Better to write "*Nothing here that a static explanation didn't already cover.*" than to add a diagram that decorates rather than teaches.
- **A single mega-diagram of the whole subsystem.** Split into two focused figures or drop the sprawling one.
- **Filesystem order in the code walk.** Semantic order is non-negotiable — it's the whole point of the "literate" framing.
- **Skipping the per-file prose paragraph.** Without it, Section 4 is just a colored grep dump — you've defeated the point.
- **Prose that echoes the code.** "`x = foo()` — this assigns the return of `foo` to `x`" is worse than nothing. Prose is for *why*, code is for *what*.
- **Padding.** Every paragraph must be one the reader would miss if you removed it. If a paragraph could be deleted with no loss to understanding, delete it.
- **Printing customer / client data** — never reprint real user names, hostnames, IPs, tokens, or company names, even if they appear in the code you're walking.
- **Posting the output to the PR platform** (as a PR comment or issue). Delivery is chat + optional durable save only. `explain-topic` is not tied to a diff or a PR.
- **Searching the durable store for the parent page** each run. Hardcode the parent ID / path once at setup. Do not call `search` for it every time.
- **Reading only file names.** You cannot write good Intro or good per-file prose without reading the actual code — this is step 1's mandatory whole-file reads.
