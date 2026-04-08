from __future__ import annotations

from datetime import datetime

import pytest

from src.models.schemas import RiskLevel, RepoVisibility
from src.services.risk_scoring import compute_risk_level, compute_risk_score
from src.config import settings


@pytest.mark.parametrize(
    "score,expected",
    [
        (0.0, RiskLevel.low),
        (29.9, RiskLevel.low),
        (30.0, RiskLevel.medium),
        (59.9, RiskLevel.medium),
        (60.0, RiskLevel.high),
        (79.9, RiskLevel.high),
        (80.0, RiskLevel.critical),
        (100.0, RiskLevel.critical),
    ],
)
def test_compute_risk_level_thresholds(score: float, expected: RiskLevel) -> None:
    assert compute_risk_level(score) == expected


def test_compute_risk_score_bounds() -> None:
    risk = compute_risk_score(
        repo_full_name="acme/example",
        commits_last_window=0,
        open_prs=0,
        open_issues=0,
        visibility=RepoVisibility.public,
        repo_size_kb=0,
        last_pushed_at=None,
    )
    assert 0.0 <= risk.risk_score <= 100.0


def test_risk_score_monotonic_commits() -> None:
    cfg = settings.model_copy(update={"enable_stability_penalty": False})

    r0 = compute_risk_score(
        repo_full_name="acme/example",
        commits_last_window=0,
        open_prs=10,
        open_issues=10,
        visibility=RepoVisibility.public,
        repo_size_kb=1000,
        last_pushed_at=datetime.utcnow(),
        cfg=cfg,
    )
    r1 = compute_risk_score(
        repo_full_name="acme/example",
        commits_last_window=50,
        open_prs=10,
        open_issues=10,
        visibility=RepoVisibility.public,
        repo_size_kb=1000,
        last_pushed_at=datetime.utcnow(),
        cfg=cfg,
    )

    assert r1.risk_score >= r0.risk_score

