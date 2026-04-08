# IARG Guardian (MVP)

Intangible-Asset Risk Guardian backend service.

## Local run

The recommended way is via `docker-compose` from `IARG Implementation/` (see root `README.md`).

### Environment variables (example)

See `IARG Implementation/.env.example` for the repository-level defaults. This service additionally supports:

- `GUARDIAN_PORT` (default `8003`)
- `GUARDIAN_DB_PATH` (default `/app/data/guardian.sqlite`)
- `GITHUB_TOKEN` (required for GitHub API polling)
- `GITHUB_REPOS` (comma-separated `owner/repo` entries)
- `GUARDIAN_RISK_THRESHOLD` (default `70.0`)
- `GUARDIAN_COOLDOWN_HOURS` (default `24`)
- `GUARDIAN_SCAN_WINDOW_DAYS` (default `14`)
