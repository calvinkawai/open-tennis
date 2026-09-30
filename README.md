# Open Tennis

A private tennis learning workspace: **technical wiki + personal training wiki + a bounded, application-integrated agent**.

Read a source, ask a sourced question, adopt a training card, record what happened, and reuse that record in the next practice. The agent organizes derived wiki pages; it never overwrites the original tutorials or journal entries.

## What is implemented

- A responsive Next.js/React Web application with an installable PWA manifest and original green/gold branding.
- Technical-source import, owner-reviewed publication, original-source links, version history, Markdown export, and rollback.
- Personal records with stable submission IDs, exact-content replay checks, and durable wiki-compilation jobs.
- Automatically published **personal** wiki versions; **technical** agent proposals require explicit owner approval.
- Separate answer sections for technical support, personal observations, and unverified model supplements.
- Canonical training-card previews, explicit adoption, owner edits, and atomic plan/drill persistence.
- Explicit offline saves for pages/cards and their sources; local drafts and durable submission receipts in IndexedDB.
- A bounded Gemini adapter, restart-recoverable jobs, optional consent-aware Chroma indexing, typed errors, and privacy-conscious event logs.
- Single-owner authentication on the Web entry and every backend route, plus a private HTTPS deployment configuration.

This is a single-owner MVP, not an autonomous coach, a medical product, a match-scoring platform, or a native iOS/Android application. Store citations verify which material was used; they do **not** prove that an interpretation is technically correct.

## Content and agent permissions

| Content | Agent behavior |
| --- | --- |
| Original tutorial snapshots | Read only; imports create snapshots rather than rewriting files |
| Original journal entries | Read only; an identical submission can be replayed but not replaced |
| Personal wiki | Automatically creates a new version with original-record citations |
| Technical wiki | Creates a draft; only an explicit owner action publishes it |
| Training cards | Generates a preview; the owner adopts it |
| Model supplements | Always labeled as unverified, never promoted into technical authority |

Rollback creates an auditable new version and invalidates stale wiki jobs. A failed compilation leaves the original record intact. The current tutorial corpus is mostly forehand material; it must not be presented as complete coverage of tennis.

See [domain language](CONTEXT.md), [backend details](backend/README.md), [frontend behavior](frontend/README.md), and [private deployment](deploy/README.md).

## Local setup

Use the existing environment:

```bash
cd backend
conda activate opentennis
pip install -e . pytest pytest-asyncio pyright
```

Copy [the backend example](backend/.env.example) to an untracked `backend/.env`. Set a strong `OWNER_PASSWORD`; the default username is `owner`. Use a **new private database path**, such as `../.local/open-tennis.db`, rather than testing against the old tracked POC database.

For local development, set `PUBLIC_ORIGIN=http://localhost:3000` in both backend and frontend environments. The username/password must match on both sides.

```bash
# Terminal 1, backend/
conda activate opentennis
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-access-log
```

```bash
# Terminal 2
cd frontend
npm ci
# Copy .env.example to .env.local and set the same owner credentials.
npm run dev
```

Open `http://localhost:3000` and authenticate in the browser. Missing owner credentials fail closed with HTTP 503; unauthorized access returns HTTP 401.

1. Use **导入现有教程** to import the configured tutorial folder as drafts.
2. Open a draft, review its original citations, and explicitly approve it.
3. Ask a question or generate a training-card preview.
4. Explicitly adopt the card and record completion/observations.
5. Save locally first; confirm submission when connected.
6. Inspect the agent run, personal wiki version, and links back to the original record.

## Enabling the model

Reading and recording do not require a model key. Model use is opt-in server configuration:

```dotenv
GOOGLE_API_KEY=
AGENT_ENABLED=false
ALLOW_PERSONAL_MODEL_CONTEXT=false
SEMANTIC_INDEX_ENABLED=false
```

Set a real key and `AGENT_ENABLED=true` to allow generation. Set `ALLOW_PERSONAL_MODEL_CONTEXT=true` only after deciding that personal observations may be sent to the configured model provider. The question UI also has a per-request personal-context checkbox. Automatic personal-wiki compilation needs the server-level permission; otherwise the original is saved and the run fails visibly with a retry option.

Optional `SEMANTIC_INDEX_ENABLED=true` builds a **separate** wiki Chroma collection. It indexes only approved technical evidence and, when permitted, original personal records. It does not index unapproved technical drafts or treat generated summaries as independent evidence. With indexing disabled/pending/failed, answers explicitly disclose local-text retrieval instead of silently claiming semantic search.

The default model is `gemini-2.5-flash`, with bounded request time, retry count, input size, and output tokens. An enabled model still incurs provider usage charges. There is no model fine-tuning and no background web crawling.

## Offline behavior

- Save a page or card explicitly to keep its original sources and provenance offline.
- Practice completion is written to a device-local draft.
- Text edits show whether they are saved; use **保存到本机** before leaving.
- Reconnecting never uploads drafts automatically.
- A submission is removed from drafts only after the matching server acknowledgement is durably recorded locally.
- Lost acknowledgements retry with the same ID and payload, not a new record.
- Export private local data before clearing it. Browser/OS eviction may remove unsubmitted drafts; local storage is **not a backup**.
- New AI operations require connectivity. The PWA does not rely on continuous background execution or background sync.

Basic authentication protects online data, not copies already saved on a trusted personal device.

## Validation

```bash
cd backend
conda activate opentennis
python -m pytest -q
python -m pyright --pythonpath "$CONDA_PREFIX/bin/python"
```

```bash
cd frontend
npm test
npm run typecheck
NEXT_TELEMETRY_DISABLED=1 npm run build
```

Tests use synthetic material and isolated SQLite/Chroma directories. They cover original-record preservation, duplicate submissions, technical review, stale writes and rollback, canonical citations, plan adoption, database upgrades/restoration, API authentication, UI evidence separation, and offline drafts.

Browser integration has also been exercised against the real backend/frontend with an injected test model. This validates the product wiring, **not real-model coaching quality**. Live-provider evaluation, actual iPhone/Android installation, and deployment under your own HTTPS domain remain separate release checks.

## Private deployment and data

[Deploy with persistent storage and HTTPS](deploy/README.md). Do not put SQLite or Chroma in ephemeral serverless function storage, expose the backend port publicly, or place provider keys in `NEXT_PUBLIC_*` variables.

Back up before upgrading an existing database:

```bash
cd backend
conda activate opentennis
python -m app.cli.backup --source /private/path/open-tennis.db \
  --output /private/path/open-tennis-backup.db
```

The output path must not exist. The same command can restore a backup into a **new** database; point the application at that file after verifying it. Chroma is derived and can be rebuilt. Keep database copies private because they contain original notes and source snapshots.
