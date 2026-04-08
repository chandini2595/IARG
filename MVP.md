# IARG MVP - Intangible-Asset Risk Guardian

This MVP adds an end-to-end “Guardian” loop:
GitHub activity -> explainable risk score -> simulated insurance purchase -> stored claim evidence.

**Additional requirement — Google Drive:** monitored Drive resources (identified by file or folder ID) can raise **breach** events (data exposure, unauthorized access, ransomware, etc.). When a breach is reported to the Guardian, insurance is **evaluated immediately** with a critical synthetic risk score; the normal GitHub activity threshold is **bypassed** (cooldown and policy bands still apply). In production, connect Google Workspace Alert Center, DLP, or an admin webhook to `POST /api/guardian/google-drive/breach`.

## 1. Prerequisites

- Docker + Docker Compose
- Node.js >= 18 (for the dashboard)

## 2. Configure environment variables

From the `IARG Implementation/` folder:

```bash
cd "IARG Implementation"
cp .env.example .env
```

Set at least:

- `GITHUB_TOKEN` (required for GitHub REST API polling)
- `GITHUB_REPOS` (comma-separated `owner/repo` list; used when the UI scan request does not provide candidates)

Optional:

- `RISK_THRESHOLD` (default `70.0`)
- `COOLDOWN_HOURS` (default `24`)
- `SCAN_WINDOW_DAYS` (default `14`)
- `DRIVE_BREACH_WEBHOOK_SECRET` — if set, breach requests and `POST .../monitor/poll-now` must send header `X-IARG-Drive-Breach-Secret`
- `DRIVE_BREACH_SYNTHETIC_RISK_SCORE` (default `95.0`) — score used for breach-triggered insurance (≥ 80 uses the parametric policy template)
- **Google Drive API monitor (optional):** `GOOGLE_DRIVE_MONITOR_ENABLED=true`, `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, `GOOGLE_DRIVE_REFRESH_TOKEN` (see script below), `GOOGLE_DRIVE_MONITORED_IDS` (comma-separated file/folder IDs). Optional tuning: `GOOGLE_DRIVE_POLL_INTERVAL_SECONDS`, `GOOGLE_DRIVE_FOLDER_MAX_CHILDREN`, `GOOGLE_DRIVE_ALLOWED_EMAIL_DOMAINS`, `GOOGLE_DRIVE_FLAG_DOMAIN_SHARES`.

## 3. Run the stack (Guardian + services + dashboard)

```bash
cd "IARG Implementation"
npm install
npm run dev
```

What you should see:

- Backend services via Docker Compose (Kafka/Neo4j/Redis/Guardian/etc.)
- Dashboard dev server at `http://localhost:3000`

## 4. Trigger a scan

You can do this either from the UI or via the Guardian backend.

### UI

1. Open `http://localhost:3000/settings`
2. Paste candidate repos (`owner/repo,owner/repo,...`)
3. Choose `Risk Threshold` and `Window Days`
4. Click **Run Scan & Evaluate**

### Backend API (direct)

```bash
curl -X POST http://localhost:8003/api/guardian/scan/now \
  -H "Content-Type: application/json" \
  -d '{"candidate_repos":["facebook/react","tensorflow/tensorflow"],"threshold":70,"window_days":14}'
```

### Google Drive breach → insurance

Report an incident for a Drive file or folder (resource ID from the Drive URL or API). Insurance triggers if cooldown allows and the synthetic score matches a policy band (default score 95 → parametric tier).

```bash
curl -X POST http://localhost:8003/api/guardian/google-drive/breach \
  -H "Content-Type: application/json" \
  -H "X-IARG-Drive-Breach-Secret: YOUR_SECRET_IF_CONFIGURED" \
  -d '{"resource_id":"YOUR_DRIVE_FILE_OR_FOLDER_ID","breach_category":"data_exposure","description":"Optional details"}'
```

### Google Drive API — ACL polling (infer risky sharing)

Guardian can call the **Google Drive API** (read-only OAuth) on a schedule, snapshot `permissions` per monitored file/folder, and compare to the previous poll. **New** permissions that match risk rules can automatically invoke the same insurance path as a manual breach report.

1. Enable **Drive API** and create an **OAuth 2.0 Client ID** (Desktop) in [Google Cloud Console](https://console.cloud.google.com/).
2. From `app/guardian` after `pip install -r requirements.txt`:

   ```bash
   export GOOGLE_DRIVE_CLIENT_ID="...apps.googleusercontent.com"
   export GOOGLE_DRIVE_CLIENT_SECRET="..."
   python scripts/google_drive_oauth_refresh_token.py
   ```

3. Put the printed `GOOGLE_DRIVE_REFRESH_TOKEN` in `.env`, set `GOOGLE_DRIVE_MONITORED_IDS` (e.g. your folder ID), and `GOOGLE_DRIVE_MONITOR_ENABLED=true`. Rebuild/restart Guardian.

**Rules (MVP):**

- **Baseline:** the first successful poll for each resource only stores ACLs; it does **not** trigger insurance.
- **New `anyone` permission** → treated as **data_exposure** (public / “anyone with the link” style access).
- **New `user` permission** → triggers only if `GOOGLE_DRIVE_ALLOWED_EMAIL_DOMAINS` is non-empty and the invitee’s email domain is **not** in that list (**unauthorized_access**).
- **New `domain` permission** → triggers only if `GOOGLE_DRIVE_FLAG_DOMAIN_SHARES=true` (can be noisy).

For a **folder** ID, Guardian checks that folder’s ACL and up to `GOOGLE_DRIVE_FOLDER_MAX_CHILDREN` **direct children** (not deep recursion).

**Endpoints:**

- `GET http://localhost:8003/api/guardian/google-drive/monitor/status` — config + last poll metadata
- `POST http://localhost:8003/api/guardian/google-drive/monitor/poll-now` — run one poll immediately (same webhook secret header as manual breach, if configured)

The dashboard **Settings** page shows monitor status and a **Run ACL poll now** button.

## 5. Inspect results

- Latest risk:
  - `GET http://localhost:8003/api/guardian/risk/latest`
- Monitor summary:
  - `GET http://localhost:8003/api/guardian/monitor/summary`
- Insurance purchases (latest first):
  - `GET http://localhost:8003/api/guardian/insurance/purchases`
- Evidence for a specific purchase:
  - `GET http://localhost:8003/api/guardian/insurance/purchases/<purchase_id>`

## Notes / MVP behavior

- The Guardian selects the repo with the highest “activity score” (commits + open PRs + open issues over the scan window).
- If the selected repo’s `risk_score` is `> risk_threshold` and cooldown allows, it triggers one of the built-in policy templates:
  - `micro_policy` for high risk (60–79.999)
  - `parametric_policy` for critical risk (>= 80)
- Insurance purchases and evidence are stored in the Guardian SQLite DB at `/app/data/guardian.sqlite` (persisted via the `guardian_data` Docker volume).
- Google Drive assets are keyed as `gdrive/<resource_id>` in purchase and monitor records alongside GitHub `owner/repo` strings.
- Drive **API** detections set `detection_source: drive_api_poll` in stored evidence; manual/UI reports use `manual`.
