from __future__ import annotations

import json
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    debug: bool = False
    port: int = 8003
    cors_origins: List[str] = ["http://localhost:3000"]

    # GitHub polling
    github_token: str = ""
    # Keep as string to avoid pydantic-settings forcing JSON parsing for List types.
    # Accepts:
    # - JSON array: ["owner/repo","owner2/repo2"]
    # - comma-separated: owner/repo,owner2/repo2
    github_repos: str = ""
    github_max_pages: int = 10

    # Scan config
    scan_window_days: int = 14

    # Risk scoring normalization
    max_commits_for_norm: int = 100
    max_open_prs_for_norm: int = 50
    max_open_issues_for_norm: int = 200
    max_repo_size_kb_for_norm: int = 100000

    # Exposure proxy
    exposure_public_weight: float = 0.6
    exposure_size_weight: float = 0.4

    # Stability penalty (optional)
    enable_stability_penalty: bool = False
    stale_days_threshold: int = 180

    # Guardian behavior
    risk_threshold: float = 70.0
    cooldown_hours: int = 24

    # Risk model selection
    # - "heuristic": current rule-based scoring
    # - "xgb-demo": trains an XGBoost regressor on synthetic teacher data (demo-only)
    risk_model_type: str = "heuristic"
    xgb_model_path: str = "/app/model/xgb_risk_model.json"
    xgb_demo_samples: int = 2000

    # Evidence collection limits
    evidence_max_commits: int = 5
    evidence_max_prs: int = 5
    evidence_max_issues: int = 5

    # Persistence
    db_path: str = "/app/data/guardian.sqlite"

    # Google Drive — OAuth (user-delegated) for API monitor
    # Create OAuth client in Google Cloud Console (Desktop app), then run:
    #   python scripts/google_drive_oauth_refresh_token.py
    google_drive_monitor_enabled: bool = False
    google_drive_client_id: str = ""
    google_drive_client_secret: str = ""
    google_drive_refresh_token: str = ""
    # Comma-separated file or folder IDs to poll (folder = that folder + direct children)
    google_drive_monitored_ids: str = ""
    google_drive_poll_interval_seconds: int = 300
    google_drive_folder_max_children: int = 50
    # If non-empty (comma-separated domains), new "user" shares to emails outside these domains trigger
    google_drive_allowed_email_domains: str = ""
    # If True, new broad "domain" type permissions (whole domain access) trigger
    google_drive_flag_domain_shares: bool = False

    # Google Drive — breach notifications (Workspace alerts, DLP, or admin integration)
    # When set, POST /api/guardian/google-drive/breach must send header
    # X-IARG-Drive-Breach-Secret with this value.
    drive_breach_webhook_secret: str = ""
    # Synthetic score used for breach-triggered insurance (>= 80 selects parametric policy).
    drive_breach_synthetic_risk_score: float = 95.0

    @property
    def github_repos_list(self) -> List[str]:
        s = (self.github_repos or "").strip()
        if not s:
            return []

        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass

        return [part.strip() for part in s.split(",") if part.strip()]

    @property
    def google_drive_monitored_ids_list(self) -> List[str]:
        return [x for x in (self.google_drive_monitored_ids or "").replace(" ", "").split(",") if x]

    @property
    def google_drive_allowed_email_domains_set(self) -> set[str]:
        parts = [p.strip().lower().lstrip("@") for p in (self.google_drive_allowed_email_domains or "").split(",")]
        return {p for p in parts if p}


settings = Settings()

