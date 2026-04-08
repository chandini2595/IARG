from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from src.models.schemas import RiskScoreResult


class EvidenceService:
    async def collect_evidence(
        self,
        *,
        github_client: Any,
        repo_full_name: str,
        risk: RiskScoreResult,
        metrics: Dict[str, Any],
        evidence_max_commits: int,
        evidence_max_prs: int,
        evidence_max_issues: int,
        now: datetime,
    ) -> Dict[str, Any]:
        owner, name = repo_full_name.split("/", 1)

        recent_commits = await github_client.get_recent_commits(
            owner=owner,
            repo=name,
            limit=evidence_max_commits,
        )
        open_prs = await github_client.get_top_open_prs(
            owner=owner,
            repo=name,
            limit=evidence_max_prs,
        )
        open_issues = await github_client.get_top_open_issues(
            owner=owner,
            repo=name,
            limit=evidence_max_issues,
        )

        return {
            "collected_at": now.isoformat(),
            "repo_full_name": repo_full_name,
            "risk_explanation": risk.breakdown.explanation,
            "metrics_used": metrics,
            "recent_commits": [
                {"sha": c["sha"], "message": c["message"], "committed_at": c.get("date")} for c in recent_commits
            ],
            "top_open_prs": [{"pr_number": p["number"], "title": p["title"]} for p in open_prs],
            "top_open_issues": [{"issue_number": i["number"], "title": i["title"]} for i in open_issues],
        }

