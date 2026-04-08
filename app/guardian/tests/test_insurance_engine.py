from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.config import settings
from src.models.schemas import RiskLevel
from src.services.insurance_engine import InsuranceEngine
from src.services.storage import Storage


@pytest.mark.asyncio
async def test_cooldown_prevents_second_purchase(tmp_path) -> None:
    db_path = str(tmp_path / "guardian.sqlite")
    storage = Storage(db_path)
    await storage.init()

    cfg = settings.model_copy(update={"cooldown_hours": 24, "risk_threshold": 50.0, "enable_stability_penalty": False})
    engine = InsuranceEngine(storage, cfg=cfg)

    repo = "acme/example"
    triggered_at_1 = datetime(2026, 1, 1, 0, 0, 0)

    await storage.create_purchase_with_evidence(
        repo_full_name=repo,
        policy_id="parametric_policy",
        policy_name="Parametric Policy (Critical Risk)",
        triggered_risk_score=90.0,
        triggered_risk_level=RiskLevel.critical.value,
        premium=5000.0,
        payout=100000.0,
        triggered_at=triggered_at_1,
        evidence={"dummy": True},
    )

    plan = await engine.plan_purchase(
        repo_full_name=repo,
        risk_score=90.0,
        risk_level=RiskLevel.critical,
        now=triggered_at_1 + timedelta(hours=1),
        threshold=50.0,
    )

    assert plan["allowed"] is False
    assert plan["cooldown_applied"] is True


@pytest.mark.asyncio
async def test_threshold_allows_purchase_when_above_threshold(tmp_path) -> None:
    db_path = str(tmp_path / "guardian.sqlite")
    storage = Storage(db_path)
    await storage.init()

    cfg = settings.model_copy(update={"cooldown_hours": 24, "risk_threshold": 50.0, "enable_stability_penalty": False})
    engine = InsuranceEngine(storage, cfg=cfg)

    plan = await engine.plan_purchase(
        repo_full_name="acme/example",
        risk_score=90.0,
        risk_level=RiskLevel.critical,
        now=datetime(2026, 1, 1, 0, 0, 0),
        threshold=50.0,
    )

    assert plan["allowed"] is True
    assert plan["triggered"] is True


@pytest.mark.asyncio
async def test_ignore_threshold_allows_below_config_threshold(tmp_path) -> None:
    db_path = str(tmp_path / "guardian.sqlite")
    storage = Storage(db_path)
    await storage.init()

    cfg = settings.model_copy(update={"cooldown_hours": 24, "risk_threshold": 80.0, "enable_stability_penalty": False})
    engine = InsuranceEngine(storage, cfg=cfg)

    plan = await engine.plan_purchase(
        repo_full_name="acme/example",
        risk_score=65.0,
        risk_level=RiskLevel.high,
        now=datetime(2026, 1, 1, 0, 0, 0),
        threshold=None,
        ignore_threshold=False,
    )
    assert plan["allowed"] is False
    assert plan.get("reason") == "below_threshold"

    plan2 = await engine.plan_purchase(
        repo_full_name="acme/other",
        risk_score=65.0,
        risk_level=RiskLevel.high,
        now=datetime(2026, 1, 1, 0, 0, 0),
        threshold=None,
        ignore_threshold=True,
    )
    assert plan2["allowed"] is True

