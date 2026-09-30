# Open Tennis Web / PWA

One responsive Next.js/React application, backed by the private FastAPI server.

```bash
npm ci
# Copy .env.example to .env.local, then set matching backend owner credentials.
npm run dev
```

`OWNER_USERNAME`, `OWNER_PASSWORD`, `PUBLIC_ORIGIN`, and `BACKEND_ORIGIN` are server-only settings. Never use `NEXT_PUBLIC_*` for credentials. Missing credentials fail closed; all data operations use same-origin authenticated routes. The API proxy enforces JSON writes and same-origin protection.

## Views

- **技术 Wiki**: source browser, original citations, questions, technical approval, differences/version inspection, and rollback.
- **训练卡**: generated preview, explicit adoption, owner edits, practice completion, and entry into a local journal draft.
- **我的 Wiki**: personal topics linked to unchanged original records and agent status.
- **本机草稿 / 离线设置**: saved pages/cards/sources, local drafts, submission receipts, private JSON export, and explicitly confirmed device-data clearing.

Source-supported text, original personal observations, and unverified model supplements remain visually distinct. Markdown does not execute raw HTML or automatically fetch remote images.

## Offline invariants

The service worker caches only the generic application shell/static resources. It never caches agent/write requests or automatically uploads records. Private pages, source snapshots, and cards enter IndexedDB only through explicit save actions.

Submission requires owner confirmation and a stable client ID. A draft is locked once a submission is attempted; the same payload is used after a lost acknowledgement. The matching server receipt is stored before the local draft is removed.

Text edits display unsaved status and have an explicit local-save button. Connection changes do not discard editor text. Browser/OS storage eviction is outside the app's control; export important drafts. Being installed to the home screen does not make new AI calls work offline.

PWA installation requires a supported browser and HTTPS (localhost is a development exception). Actual iOS/Android installation and authentication persistence must be tested on the intended devices; desktop browser emulation is not a substitute.

A same-Wi-Fi HTTP preview can browse and create local drafts using cryptographically generated submission IDs even where `crypto.randomUUID` is unavailable. It does not enable service workers or offline app reopening on that origin. HTTP does not encrypt credentials or records: use isolated demo data and a temporary preview password only, never personal production data.

## Checks

```bash
npm test
npm run typecheck
NEXT_TELEMETRY_DISABLED=1 npm run build
```

Tests cover response shapes, non-JSON auth failures, source-ID encoding, draft reopening, lost-acknowledgement replay, no automatic reconnect uploads, explicit source-bundle saving, text safety, owner review, network-change preservation, and proxy origin handling.

Original PWA icons are checked in. Regenerate them with `npm run icons` after changing `public/icon.svg`.
