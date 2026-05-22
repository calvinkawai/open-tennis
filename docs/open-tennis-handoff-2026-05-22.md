# Open Tennis Backend RAG Handoff

Date: 2026-05-22  
Audience: classmate / collaborator review  
Repository: `https://github.com/calvinkawai/open-tennis.git`  
Branch: `guoqing`  
Latest commit: `07c53c1 Implement RAG plan generation retrieval`  
PR link: `https://github.com/calvinkawai/open-tennis/pull/new/guoqing`

## Summary

Yesterday, 2026-05-21, the backend POC was completed for the Open Tennis RAG training-plan flow:

`user query -> Chroma retrieval -> Gemini generation -> optional SQLite persistence -> CLI/API response`

The work is pushed to `origin/guoqing`. The main implementation details should be reviewed from the commit/diff rather than duplicated here.

## What Changed

- Added the backend vertical slice for generating tennis training plans from a natural-language query.
- Added FastAPI plan endpoints:
  - `POST /api/v1/plans`
  - `GET /api/v1/plans`
  - `GET /api/v1/plans/{id}`
- Added CLI preview:
  - `python -m app.cli.generate_plan "My forehand is weak"`
  - `python -m app.cli.generate_plan "My forehand is weak" --show-context`
- Added centralized settings for Gemini, embeddings, Chroma, SQLite, and retrieval parameters.
- Added Gemini LLM service using structured output with fields:
  - `title`
  - `focus_area`
  - `raw_ai_content`
  - `drills`
- Added rendering so CLI/API responses show a normalized human-readable training plan.
- Rebuilt retrieval from whole-file markdown indexing to structured tutorial chunks:
  - one `technical_detail` chunk per tutorial
  - one `segment` chunk per tutorial segment
  - excluded `Cartoon Card`
  - Chroma collection metadata uses cosine: `{"hnsw:space": "cosine"}`
- Added lightweight reranking in `VectorService`:
  - fetches more Chroma candidates than final `RETRIEVAL_K`
  - combines vector distance with keyword overlap in segment title, cue, visual focus, and content
  - limits repeated chunks from the same source tutorial
- Rebuilt `backend/data/chroma_db` with 58 section-level chunks.

## Important Files

Review these first:

- `backend/app/services/vector.py`: Chroma retrieval, rerank, `RetrievedContext`
- `backend/scripts/embed_markdowns.py`: markdown parser and Chroma rebuild script
- `backend/app/services/llm.py`: system/user prompt and Gemini structured generation
- `backend/app/services/generation.py`: retrieval -> LLM -> optional persistence wiring
- `backend/app/cli/generate_plan.py`: local terminal smoke-test entrypoint
- `backend/app/api/v1/plans.py`: public API endpoints
- `backend/app/core/config.py`: env-driven settings

## How To Run Locally

Prerequisites:

- Use the existing conda env: `opentennis`
- Add Gemini credentials through local env or untracked `backend/.env`
- Do not commit API keys

From `backend/`:

```bash
conda run -n opentennis python -m compileall app main.py scripts
```

CLI smoke:

```bash
conda run -n opentennis python -m app.cli.generate_plan "My forehand is weak"
conda run -n opentennis python -m app.cli.generate_plan "My forehand is weak" --show-context
```

Rebuild Chroma if needed:

```bash
conda run -n opentennis python scripts/embed_markdowns.py --docs-path data/tutorial --database-path data/chroma_db --reset
```

Expected Chroma result:

- collection: `tennis_tutorial_sections`
- count: `58`
- metadata: `{"hnsw:space": "cosine"}`

## Verification Already Done

These checks were run before commit/push:

- `conda run -n opentennis python -m compileall app main.py scripts`
- `git diff --check`
- Chroma rebuild with Gemini embeddings
- Retrieval smoke queries:
  - `My forehand is weak`
  - `I hit forehands under the net`
  - `How do I improve wrist lag?`
  - `I need more forehand power`
- CLI smoke with and without `--show-context`
- API smoke using a temporary SQLite DB:
  - `POST /api/v1/plans` returned `201`
  - `GET /api/v1/plans` returned `200`
  - `GET /api/v1/plans/{id}` returned `200`
  - response included `rendered_text`

## Known Notes

- No frontend work was included.
- No DB migration was added.
- `video_url` is usually `null` because current tutorial markdown files do not include URLs.
- Retrieval reranking is intentionally lightweight and heuristic. It is good enough for the POC, but future work could add formal evals or a model-based reranker.
- The generated Chroma index is committed on `guoqing`; reviewers should expect binary diffs in `backend/data/chroma_db`.

## Suggested Skills

- `superpowers:verification-before-completion`: use before claiming any review or follow-up change is complete.
- `superpowers:systematic-debugging`: use if Chroma, Gemini, or API smoke checks fail.
- `gh-address-comments` / `github:gh-address-comments`: use when responding to PR review comments.
- `handoff`: use again if another session needs a compact continuation summary.

