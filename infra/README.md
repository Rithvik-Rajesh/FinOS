# Infra

Everything needed to run FinOS.

```
infra/
├── compose/
│   └── dev.yml        # local stack: Postgres 16, Redis 7, MinIO (+ bucket bootstrap)
├── docker/            # (future) production Dockerfiles / overrides
├── ci/                # (future) pipeline definitions beyond .github/workflows
├── provisioning/      # (future) VPS bootstrap, TLS (Caddy), backups, restore runbook
└── observability/     # (future) logging/metrics/uptime config
```

## Local stack

From the repo root:

```bash
make up      # start postgres, redis, minio (creates .env from .env.example first)
make logs    # tail
make down    # stop
make nuke    # stop + delete volumes (destroys local data)
```

Services (dev):

| Service | URL / port | Notes |
|---|---|---|
| Postgres | `localhost:5432` | user/pass/db from `.env` |
| Redis | `localhost:6379` | Celery broker + cache |
| MinIO API | `localhost:9000` | S3-compatible object storage |
| MinIO console | `localhost:9001` | web UI (root creds from `.env`) |

The `minio-setup` one-shot container creates the attachments bucket and exits.

## Production (later)

VPS + Docker Compose with Caddy for TLS, encrypted volumes, and an encrypted offsite
backup job. Provisioning scripts and the restore runbook live under `provisioning/`
(added in Phase 0 hardening). See [../SECURITY.md](../SECURITY.md).
