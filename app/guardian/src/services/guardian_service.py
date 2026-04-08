from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from src.config import Settings, settings
from src.models.schemas import (
    RepoVisibility,
    RiskBreakdown,
    RiskLevel,
    RiskScoreResult,
)
from src.services.evidence_service import EvidenceService
from src.services.github_client import GitHubClient
from src.services.insurance_engine import InsuranceEngine
from src.services.risk_scoring import (
    compute_activity_score_for_selection,
    compute_risk_score,
)
from src.services.storage import Storage


class GuardianService:
    def __init__(self, storage: Storage, cfg: Settings = settings):
        self.storage = storage
        self.cfg = cfg
        self.github = GitHubClient(cfg)
        self.evidence = EvidenceService()
        self.insurance = InsuranceEngine(storage, cfg)

    async def close(self) -> None:
        await self.github.close()

    async def scan_now(
        self,
        *,
        candidate_repos: List[str],
        threshold: float,
        window_days: int,
    ) -> Dict[str, Any]:
        """
        1) Fetch activity metrics for all candidate repos.
        2) Select most active repo using (normalized commits, open PRs, open issues).
        3) Compute risk score for the selected repo.
        4) If risk score crosses threshold and cooldown allows: trigger insurance and collect evidence.
        """
        now = datetime.utcnow()

        repo_metrics: Dict[str, Dict[str, Any]] = {}
        repo_activity_scores: Dict[str, float] = {}
        repo_risks: Dict[str, RiskScoreResult] = {}

        # MVP: sequential collection to keep GitHub rate usage simple and deterministic.
        # Later we can parallelize with asyncio.gather once stability is proven.
        for repo_full_name in candidate_repos:
            owner, name = repo_full_name.split("/", 1)
            repo_info = await self.github.get_repo(owner=owner, repo=name)

            visibility = RepoVisibility.private if repo_info.get("private") is True else RepoVisibility.public
            repo_size_kb = int(repo_info.get("size") or 0)
            pushed_at_str = repo_info.get("pushed_at")
            last_pushed_at = None
            if pushed_at_str:
                last_pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))

            commits_last_window = await self.github.count_commits_last_window(
                owner=owner,
                repo=name,
                window_days=window_days,
            )
            open_prs = await self.github.count_open_prs(owner=owner, repo=name)
            open_issues = await self.github.count_open_issues(owner=owner, repo=name)

            metrics = {
                "repo_full_name": repo_full_name,
                "visibility": visibility.value,
                "repo_size_kb": repo_size_kb,
                "last_pushed_at": last_pushed_at.isoformat() if last_pushed_at else None,
                "commits_last_window": commits_last_window,
                "open_prs": open_prs,
                "open_issues": open_issues,
            }
            repo_metrics[repo_full_name] = metrics

            activity_score = compute_activity_score_for_selection(
                commits_last_window=commits_last_window,
                open_prs=open_prs,
                open_issues=open_issues,
                cfg=self.cfg,
            )
            repo_activity_scores[repo_full_name] = activity_score

            risk = compute_risk_score(
                repo_full_name=repo_full_name,
                commits_last_window=commits_last_window,
                open_prs=open_prs,
                open_issues=open_issues,
                visibility=visibility,
                repo_size_kb=repo_size_kb,
                last_pushed_at=last_pushed_at,
                cfg=self.cfg,
                now=now,
            )
            repo_risks[repo_full_name] = risk

        # Select most active repo (max activity score, not max risk score).
        selected_repo = max(candidate_repos, key=lambda r: repo_activity_scores.get(r, 0.0))
        selected_risk = repo_risks[selected_repo]
        selected_metrics = repo_metrics[selected_repo]

        # Record latest scan in history.
        scan_id = uuid4()
        await self.storage.record_risk_history(
            scan_id=scan_id,
            repo_full_name=selected_repo,
            scanned_at=now,
            metrics={
                "commits_last_window": selected_metrics["commits_last_window"],
                "open_prs": selected_metrics["open_prs"],
                "open_issues": selected_metrics["open_issues"],
                "visibility": selected_metrics["visibility"],
                "repo_size_kb": selected_metrics["repo_size_kb"],
                "last_pushed_at": selected_metrics["last_pushed_at"],
            },
            risk_score=selected_risk.risk_score,
            risk_level=selected_risk.risk_level.value,
            risk_explanation_json={
                "breakdown": selected_risk.breakdown.model_dump(),
                "metrics": selected_metrics,
            },
        )

        evidence_used: Optional[Dict[str, Any]] = None
        purchase_info: Optional[Dict[str, Any]] = None
        cooldown_applied = False
        skipped_reason: Optional[str] = None

        # Plan purchase first to avoid expensive evidence calls.
        plan = await self.insurance.plan_purchase(
            repo_full_name=selected_repo,
            risk_score=selected_risk.risk_score,
            risk_level=selected_risk.risk_level,
            now=now,
            threshold=threshold,
        )

        if plan.get("allowed"):
            evidence_used = await self.evidence.collect_evidence(
                github_client=self.github,
                repo_full_name=selected_repo,
                risk=selected_risk,
                metrics={
                    **selected_metrics,
                    "window_days": window_days,
                    "threshold": threshold,
                },
                evidence_max_commits=self.cfg.evidence_max_commits,
                evidence_max_prs=self.cfg.evidence_max_prs,
                evidence_max_issues=self.cfg.evidence_max_issues,
                now=now,
            )
            created = await self.storage.create_purchase_with_evidence(
                repo_full_name=selected_repo,
                policy_id=str(plan["policy_id"]),
                policy_name=str(plan["policy_name"]),
                triggered_risk_score=selected_risk.risk_score,
                triggered_risk_level=selected_risk.risk_level.value,
                premium=float(plan["premium"]),
                payout=float(plan["payout"]),
                triggered_at=now,
                evidence=evidence_used,
            )
            purchase_info = {
                "purchase_id": created["purchase_id"],
                "policy_id": plan["policy_id"],
                "policy_name": plan["policy_name"],
                "premium": plan["premium"],
                "payout": plan["payout"],
            }
        else:
            cooldown_applied = bool(plan.get("cooldown_applied", False))
            skipped_reason = plan.get("reason")

        # Update monitor state
        await self.storage.upsert_monitor_state(
            candidate_repos=candidate_repos,
            selected_repo=selected_repo,
            last_scan_at=now,
            latest_risk_score=selected_risk.risk_score,
            latest_risk_level=selected_risk.risk_level.value,
            latest_risk_json=selected_risk.model_dump(),
        )

        return {
            "scanned_at": now,
            "selected_repo": selected_repo,
            "risk": selected_risk,
            "insurance_triggered": bool(plan.get("allowed", False)),
            "purchase_id": (purchase_info or {}).get("purchase_id"),
            "cooldown_applied": cooldown_applied,
            "skipped_reason": skipped_reason,
            "selected_metrics": selected_metrics,
        }

    async def google_drive_breach(
        self,
        *,
        resource_id: str,
        breach_category: str,
        description: Optional[str] = None,
        detected_at: Optional[datetime] = None,
        detection_source: str = "manual",
        acl_evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle a reported Google Drive breach: assign critical synthetic risk, bypass the
        normal activity threshold for insurance eligibility, and persist evidence.
        Cooldown still applies per Drive resource (asset_key).
        """
        now = detected_at or datetime.utcnow()
        rid = (resource_id or "").strip()
        if not rid:
            raise ValueError("resource_id is required")

        asset_key = f"gdrive/{rid}"
        risk_score = float(self.cfg.drive_breach_synthetic_risk_score)
        risk_score = max(0.0, min(100.0, risk_score))
        risk_level = RiskLevel.critical

        synthetic_risk = RiskScoreResult(
            repo_full_name=asset_key,
            risk_score=risk_score,
            risk_level=risk_level,
            breakdown=RiskBreakdown(
                commits_norm=1.0,
                prs_norm=1.0,
                issues_norm=1.0,
                exposure_norm=1.0,
                stability_penalty=0.0,
                activity_score=1.0,
                risk_score=risk_score,
                contributions={"google_drive_breach": risk_score},
                explanation={
                    "source": "google_drive_breach",
                    "detection_source": detection_source,
                    "breach_category": breach_category,
                    "description": description,
                    "resource_id": rid,
                },
            ),
            computed_at=now,
        )

        evidence: Dict[str, Any] = {
            "source": "google_drive",
            "detection_source": detection_source,
            "asset_key": asset_key,
            "resource_id": rid,
            "breach_category": breach_category,
            "description": description,
            "synthetic_risk_score": risk_score,
            "risk_level": risk_level.value,
            "detected_at": now.isoformat(),
        }
        if acl_evidence is not None:
            evidence["acl_evidence"] = acl_evidence

        scan_id = uuid4()
        await self.storage.record_risk_history(
            scan_id=scan_id,
            repo_full_name=asset_key,
            scanned_at=now,
            metrics={
                "commits_last_window": 0,
                "open_prs": 0,
                "open_issues": 0,
                "visibility": "google_drive",
                "repo_size_kb": 0,
                "last_pushed_at": None,
            },
            risk_score=risk_score,
            risk_level=risk_level.value,
            risk_explanation_json={
                "breakdown": synthetic_risk.breakdown.model_dump(),
                "google_drive_breach": True,
                "breach_category": breach_category,
            },
        )

        trigger = await self.insurance.maybe_trigger_purchase(
            repo_full_name=asset_key,
            risk_score=risk_score,
            risk_level=risk_level,
            triggered_at=now,
            evidence=evidence,
            ignore_threshold=True,
        )

        existing = await self.storage.get_monitor_summary()
        candidate_repos: List[str] = []
        if existing and existing.get("candidate_repos_json"):
            try:
                raw = json.loads(existing["candidate_repos_json"])
                if isinstance(raw, list):
                    candidate_repos = [str(x) for x in raw]
            except Exception:
                candidate_repos = []

        if asset_key not in candidate_repos:
            candidate_repos = [*candidate_repos, asset_key]

        await self.storage.upsert_monitor_state(
            candidate_repos=candidate_repos,
            selected_repo=asset_key,
            last_scan_at=now,
            latest_risk_score=risk_score,
            latest_risk_level=risk_level.value,
            latest_risk_json=synthetic_risk.model_dump(),
        )

        return {
            "triggered_at": now,
            "asset_key": asset_key,
            "insurance_triggered": bool(trigger.get("triggered")),
            "purchase_id": trigger.get("purchase_id"),
            "cooldown_applied": bool(trigger.get("cooldown_applied", False)),
            "skipped_reason": trigger.get("reason"),
        }

