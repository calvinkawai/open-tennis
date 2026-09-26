# Open Tennis backend

FastAPI + SQLModel/SQLite + a bounded Gemini adapter. The existing CLI and one-shot plan path are retained; the application adds versioned wikis, source provenance, canonical plan adoption, and durable journal-to-wiki work.

## Run

```bash
conda activate opentennis
pip install -e . pytest pytest-asyncio pyright
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Set the values in [.env.example](.env.example) in an untracked `.env`. `OWNER_PASSWORD` is mandatory for HTTP access. `PUBLIC_ORIGIN` must be the exact browser origin, including the development port; use the same value in the frontend.

Prefer a new private `SQLITE_DATABASE_PATH`. Startup applies Alembic upgrades to that configured database. A known unversioned legacy `trainingplan`/`drill` database is recognized and preserved; unknown unversioned schemas fail closed. Back up an existing database before first startup with this version.

The legacy `app.cli.generate_plan` and `app.cli.chat_plan` still use the tutorial index configured by `CHROMA_DB_PATH`. The new app uses reviewed source snapshots in SQLite and a separate optional wiki index. Importing into the wiki does **not** silently approve a source or rebuild/delete the old index.

Imported snapshot revisions incorporate the parser revision as well as source content. A parser upgrade can therefore create a reviewable new draft without rewriting a previously published source snapshot.

## Main HTTP paths

All routes, including `/docs`, `/health`, and source exports, require owner authentication.

| Method/path | Behavior |
| --- | --- |
| `GET /api/v1/status` | Configuration/readiness, source count, pending review count |
| `POST /api/v1/wiki/import` | Import the server-configured tutorial folder into immutable source snapshots and technical drafts |
| `GET /api/v1/wiki?space=technical` | Owner-visible wiki summaries, including drafts |
| `GET /api/v1/wiki/{id}` | Current published page, or draft when there is no published version |
| `GET /api/v1/wiki/{id}/versions` | Versions and canonical original-source citations |
| `POST /api/v1/wiki/{id}/approve` | Explicit owner approval with expected current version |
| `POST /api/v1/wiki/{id}/rollback` | Auditable restore; invalidates stale agent writes |
| `POST /api/v1/wiki/{id}/propose` | Durable technical draft request, never self-approval |
| `GET /api/v1/wiki/{id}/export` | Markdown with source IDs/revisions |
| `GET /api/v1/evidence/{id}` | Original source snapshot or original journal content |
| `POST /api/v1/agent/ask` | Typed sourced answer; personal context is separately controlled |
| `POST /api/v1/plans/preview` | Store a canonical preview without adopting it |
| `POST /api/v1/plans/adopt` | Atomically adopt a stored preview; duplicate adoption returns the same card |
| `PATCH /api/v1/plans/{id}` | Owner text/drill edits without replacing original provenance |
| `GET/POST /api/v1/journal` | Read or confirm original records; stable client-ID replay protection |
| `GET /api/v1/agent/runs/{id}` | Queued/running/succeeded/failed/needs-input state |
| `POST /api/v1/agent/runs/{id}/retry` | Explicit retry of a failed wiki update |
| `POST /api/v1/wiki/reindex` | Explicit retry/rebuild of the optional semantic index |

Existing `POST /api/v1/plans`, `GET /api/v1/plans`, and `GET /api/v1/plans/{id}` remain available. Old saved plans without provenance are labeled as unverified by the new UI.

## Agent and retrieval

- One structured model operation per wiki job; no arbitrary Shell, filesystem, SQL, network, or approval tool.
- Original records and job registration commit together.
- Worker claims have expiring leases; interrupted jobs are recoverable and stale claims cannot publish.
- Source IDs/types are validated against the run's canonical evidence. Personal observations cannot become technical authority.
- Triggering and previously linked original journal citations must be retained when publishing a personal wiki update.
- Wiki updates use optimistic page versions and rollback epochs.
- Technical proposals stay drafts until explicitly approved.
- Provider/validation failures are typed and visible; original notes remain available.

The semantic index is opt-in and separate from the legacy index. Indexed originals are revalidated against current approved sources before use. Text search supports English tokens and Chinese technique aliases; semantic similarity uses a conservative heuristic cutoff, **not** a scientifically validated correctness score.

## Logging and privacy

Application event logs include request/run IDs, stage/status, error type/code, and request duration. They do not intentionally include raw prompts, journal text, credentials, or URL query strings. `--no-access-log` avoids the web server separately logging potentially personal search queries. Configure retention and access control on the deployment's logs.

`AGENT_ENABLED` and `ALLOW_PERSONAL_MODEL_CONTEXT` default to false. Setting the latter permits personal records to leave the server for configured model/embedding requests. It is not equivalent to local-only inference.

## Tests and backup

```bash
conda activate opentennis
python -m pytest -q
python -m pyright --pythonpath "$CONDA_PREFIX/bin/python"
```

Use [the backup CLI](app/cli/backup.py) to copy live SQLite consistently into a new, private file:

```bash
python -m app.cli.backup --source /path/to/current.db --output /path/to/new-backup.db
```

Never test migrations, destructive index rebuilds, or failure injection against personal production data. The test suite uses isolated temporary databases and fake model/embedding adapters.
