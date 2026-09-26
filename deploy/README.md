# Private single-owner HTTPS deployment

This directory provides a reproducible configuration, not a pre-created cloud deployment. You need a host with Docker Compose, a domain pointing to that host, and access to ports 80/443. This workspace does not supply a domain, hosting credentials, or a paid service.

## Configure and start

1. Copy [.env.example](.env.example) to an untracked `.env` **in this directory**.
2. Set `DOMAIN` to the hostname only (no scheme/path).
3. Set a strong, unique `OWNER_PASSWORD`; set `OWNER_USERNAME` if desired.
4. Initially leave all model flags false. Add your provider key and opt-in flags only when ready.
5. Build and start:

```bash
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
```

Caddy obtains and renews the TLS certificate. Only ports 80/443 are published; the backend and frontend have no direct host port mappings. Both application tiers enforce the same owner credentials. There is no public registration.

The normal Web entry, HTTP data routes, docs, original sources and exports are protected. Generic static assets/PWA metadata are public and contain no private records. Data already saved on an owner's device remains accessible offline; server authentication cannot remotely erase those copies.

## Data and runtime

- `tennis_data` stores SQLite and the derived wiki index persistently.
- Caddy has separate persistent certificate/config volumes.
- The backend runs one process/worker. Do not scale SQLite workers across independent hosts.
- Background wiki jobs are durable in SQLite; the active worker uses claim leases and optimistic wiki versions.
- The image contains tutorial inputs, but imports remain explicit owner actions and create drafts, not approved technical advice.
- Avoid ephemeral serverless function disks for this configuration.
- After startup, open `https://your-domain/`, authenticate, import sources, review and publish a source, then test one complete learning loop.

## Enable provider calls deliberately

`AGENT_ENABLED=true` enables generation and wiki compilation. `ALLOW_PERSONAL_MODEL_CONTEXT=true` permits relevant original personal records to be sent to the configured model provider. `SEMANTIC_INDEX_ENABLED=true` permits embedding of eligible original evidence. These operations can incur provider charges.

The app does not send full raw journals to a third-party analytics service. Configure local event-log retention yourself. Do not publish logs, database files, provider keys, or environment files.

## Verify before using personal data

- An unauthenticated request to `/api/v1/journal`, `/docs`, and the backend must fail.
- The public origin must be the HTTPS origin used by the browser, without a trailing path.
- Owner login should work on both desktop and the intended phone.
- Install the PWA on a real iPhone/Android device and confirm a saved card can be reopened without a network.
- Save a synthetic journal draft, reconnect, and check that no record is uploaded until explicitly confirmed.
- Confirm the raw note remains unchanged after a successful personal-wiki update.
- Confirm a technical proposal does not appear in published retrieval until approved.
- Reboot the backend and verify pending/failed work remains visible.

## Backup and restore

Use the application backup command rather than copying a live WAL database file manually:

```bash
docker compose exec backend python -m app.cli.backup \
  --output /data/open-tennis-backup-YYYY-MM-DD.db
```

The output name must be new. Copy that file to a private backup destination and test restoring it into a separate database.

```bash
docker compose exec backend python -m app.cli.backup \
  --source /data/open-tennis-backup-YYYY-MM-DD.db \
  --output /data/restored-verification.db
```

To switch production to a restored file, stop the application, configure `SQLITE_DATABASE_PATH` to that verified file, then restart. Do not overwrite or delete the current data as a shortcut. The semantic index can be rebuilt using the authenticated reindex operation.

Schema migrations are applied at startup. Back up before upgrading the image. Unknown legacy schemas are deliberately rejected instead of guessed.

## Validation limits

The configuration is provided without claiming that it has been deployed to your domain. Container build/run, TLS issuance, real-device installation, and real-provider quality should be verified in your host environment before treating this as a production service.
