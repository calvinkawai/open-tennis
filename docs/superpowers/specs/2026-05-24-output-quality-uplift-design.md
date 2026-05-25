# Output Quality Uplift — Model + Corpus

**Date:** 2026-05-24
**Status:** Design approved, ready for implementation planning

## 1. Goal & Scope

Make the generated training plans and clarifying questions noticeably better by:

1. Running both LLM calls on a stronger Gemini model.
2. Expanding the tutorial corpus beyond forehand so non-forehand queries actually retrieve relevant material.

### In scope

- Switch default `GEMINI_MODEL` from `gemini-2.5-flash-lite` to `gemini-2.5-flash` for both the reflection call (`app/services/reflection.py`) and the plan-generation call (`app/services/llm.py`).
- Add `backend/scripts/compare_models.py` to capture before/after outputs side-by-side on a fixed set of 5 queries.
- Add `backend/scripts/extract_tutorial.py` that accepts a YouTube URL or a local transcript file and emits a structured-markdown tutorial in the existing schema.
- Source and produce ~12 new tutorials (~6 serve, ~6 backhand) using the extractor + human review.
- Re-embed the corpus and validate non-forehand queries via the existing `chat_plan` CLI.

### Out of scope

- Embedding model change (current `gemini-embedding-2` works; changing it forces a full re-embed and is independent).
- Volleys, return, footwork, strategy, or fitness tutorials (later expansion).
- Switching to `gemini-2.5-pro`, automated LLM eval, or golden-file tests (deferred until simpler validation is proven insufficient).
- Any frontend or API changes.
- Fixing the latent `embed_markdowns.py` regex bug where `_extract_labeled_value` expects `**Key coaching cue:**` (bold) but existing files use unbolded labels. The cue text still ends up in chunk content; only the metadata field is empty. Worth filing as a follow-on.

## 2. Architecture & File Changes

Two independent workstreams sharing one validation hop at the end. Both are pure backend; no API or DB changes.

### Workstream A — Model upgrade

| File | Change |
|---|---|
| `backend/app/core/config.py` | Default `gemini_model` becomes `"gemini-2.5-flash"`. Env var `GEMINI_MODEL` still overrides; `gemini-2.5-flash-lite` remains available as a fallback. |
| `backend/.env.example` | Update `GEMINI_MODEL=` default to match. |
| `backend/scripts/compare_models.py` *(new)* | Runs a fixed bench of 5 queries through `ConversationService` against two models; writes `tmp/model_comparison_<timestamp>.md` with side-by-side blocks. |

### Workstream B — Corpus expansion

| File | Change |
|---|---|
| `backend/scripts/extract_tutorial.py` *(new)* | CLI that takes `--youtube-url URL` OR `--transcript-file PATH` plus `--title` / `--out-dir`. Resolves transcript, calls Gemini with the approved prompt, writes a `.md` file. |
| `backend/data/tutorial/` | Add ~6 new serve tutorials and ~6 new backhand tutorials, all produced by the extractor and human-reviewed before commit. |
| `backend/pyproject.toml` | Add `youtube-transcript-api` dependency for the URL fetch path. |

### Validation hop (after both workstreams land)

1. Re-embed: `python -m scripts.embed_markdowns --reset`.
2. Run `chat_plan` interactively with a serve query and a backhand query; confirm retrieved contexts are on-topic.
3. Re-run `compare_models.py` once on the expanded corpus.

### Boundaries

- The extractor is a one-shot script (input → transcript → LLM call → markdown file). No coupling to `ConversationService` or `LLMService`.
- `compare_models.py` reuses `ConversationService` as a black box; only varies `GEMINI_MODEL` per run. No production code changes required for it to work.
- The model upgrade is a single config default change; the env-var override keeps rollback instant.

## 3. Extractor — Prompt & Pipeline

Use the user's existing NotebookLM prompt (proven on the 15 forehand tutorials) almost verbatim in `extract_tutorial.py`.

### Prompt (verbatim from user)

```
Analyze this tennis instruction video. Focus only on the core technique taught.
Ignore intro, ads, jokes, and filler. Do not invent details.

Produce THREE markdown sections:

## 1. Video Summary

**Technical Detail:** Summarize the technique in concise bullet points.

## 2. Segments

For each topic-based segment:

- **Title**
- 1–2 sentence technical summary
- Key coaching cue (quote only if exact)
- Visual focus: what to watch in body, racket, or ball

## 3. Cartoon Card (4 Steps)

For each step:

- **Step N: Title**
- Instruction: one imperative sentence, ≤15 words
- Visual: body position, racket, ball, motion arrows, one common-error ✗ mark
---
Markdown only. Coaching voice. No filler. No unsupported claims.
```

### Three small additions to the prompt for in-repo use

1. **Segment headers** should be `**Segment N: <Title>**` (the "Segment N:" prefix matches existing files and aids future tooling).
2. **Bullet style** should be `*   ` (asterisk + three spaces) for sub-bullets to match existing formatting.
3. **No closing chit-chat:** "Output only the three sections. No preamble, no closing summary."

### Pipeline

```
input (--youtube-url OR --transcript-file)
  → resolve transcript (youtube-transcript-api fetch OR file read)
  → call Gemini with the prompt + transcript + tutorial title
  → write data/tutorial/<title>.md
  → optional regex sanity check (## 1., ## 2. Segments, ≥1 **Segment line)
  → print "Review before committing" to stderr
```

No Pydantic schema, no renderer, no auto-embed. The script writes the file and stops; human reviews before re-running `embed_markdowns.py --reset`.

## 4. Model Comparison Script

### Design

CLI: `python -m scripts.compare_models [--models lite,flash] [--out tmp/]`

A fixed bench of ~5 representative queries is hardcoded in the script:

```python
QUERIES = [
    "My forehand sails long under pressure",         # corpus-strong (forehand)
    "I have trouble with my serve toss height",       # corpus-new (serve)
    "My two-handed backhand feels weak crosscourt",   # corpus-new (backhand)
    "I'm a 3.0 beginner, what should I focus on?",   # broad / vague
    "My slice backhand floats too high",              # specific weakness
]
```

For each `(query, model)` pair:

1. Set `GEMINI_MODEL` env var to the target model.
2. Run the full conversation via `ConversationService`. Auto-answer clarifying questions with a fixed reply (e.g., `"3.5 NTRP, plays twice a week, partner-based practice"`) so outputs are reproducible.
3. Capture every clarifying question + the final plan (title, focus_area, raw_ai_content, drills).
4. Write `tmp/model_comparison_<YYYYMMDD-HHMMSS>.md` with side-by-side blocks.

### Output shape (per query)

```markdown
## Query: "<the query>"

### gemini-2.5-flash-lite
- Q1: <question>
- Q2: <question>
- Plan title: ...
- raw_ai_content:
  ...
- Drills:
  1. ...

### gemini-2.5-flash
- Q1: <question>
- Plan title: ...
- raw_ai_content:
  ...
- Drills:
  1. ...
```

### Validation sequence

1. Land Workstream A (config default flip + `compare_models.py`).
2. Run `compare_models.py` — baseline showing flash vs flash-lite on the *current* corpus.
3. Land Workstream B (extractor + ~12 new tutorials).
4. Re-embed: `python -m scripts.embed_markdowns --reset`.
5. Run `chat_plan` interactively with a serve query and a backhand query.
6. Re-run `compare_models.py` to capture flash vs flash-lite on the *expanded* corpus.

## 5. Testing, Error Handling, Risks

### Testing

- **Model upgrade:** no new unit tests. Behavioral validation is `compare_models.py` output.
- **Extractor:** one small test using a fixture transcript. Stub the LLM call; assert the written `.md` passes the same regex checks `embed_markdowns.py` uses (`## 1.`, `## 2. Segments`, at least one `**Segment` line).
- **compare_models.py:** utility script, not tested. Manual sanity-check on first run.
- Existing 12 tests must continue to pass. The model default change shouldn't affect them (tests stub the invoker).

### Error handling

- **Extractor URL fetch:** if `youtube-transcript-api` fails (no captions, age-restricted, etc.), print a clear message and instruct the user to fall back to `--transcript-file`. Do not auto-retry or scrape.
- **Extractor LLM call:** rely on Gemini's failure modes. If output is unusable, raise — user sees the traceback and reruns with a different prompt or model.
- **compare_models.py:** if one model fails for one query (rate limit, transient error), record the error in the output markdown cell and continue. Partial output beats nothing.

### Risks & mitigations

- **`gemini-2.5-flash` free-tier rate limits during compare_models.py:** bench is ≤10 calls per model. If it bites, rerun with smaller `--models` subset.
- **Generated tutorial quality variance:** mandatory human review before commit. The extractor writes the file and prints a review reminder rather than auto-embedding.
- **Schema drift between extractor output and existing markdowns:** regex sanity check catches obvious gaps. Deeper safety net: if `embed_markdowns.py --reset` succeeds on the new files, the format is good enough.
- **Sourcing block:** finding 12 high-quality serve/backhand tutorials may take longer than the engineering. This spec does not solve the sourcing task; it is treated as a content effort the user runs in parallel.

## 6. Implementation Order

1. **Workstream A** — config default change + `.env.example` update + `compare_models.py`. Land in one PR; run the comparison once to confirm the model upgrade is meaningful.
2. **Workstream B** — `extract_tutorial.py` + `youtube-transcript-api` dependency + extractor test. Land in a second PR.
3. **Content effort** (parallel with B's review): user sources ~6 serve and ~6 backhand video URLs/transcripts, runs the extractor, reviews each output, drops `.md` files into `data/tutorial/`.
4. **Validation hop** — re-embed, run `chat_plan` against new topics, re-run `compare_models.py`. Capture artifacts in `tmp/` or attach to a follow-up note.

Workstream A is independently shippable. Workstream B + content effort can land later without blocking A.
