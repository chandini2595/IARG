from __future__ import annotations

import pytest

from src.config import settings
from src.services.guardian_service import GuardianService
from src.services.storage import Storage


@pytest.mark.asyncio
async def test_google_drive_breach_triggers_insurance_despite_high_threshold(tmp_path) -> None:
    db_path = str(tmp_path / "guardian.sqlite")
    storage = Storage(db_path)
    await storage.init()

    cfg = settings.model_copy(
        update={
            "risk_threshold": 99.0,
            "cooldown_hours": 24,
            "drive_breach_synthetic_risk_score": 95.0,
            "enable_stability_penalty": False,
        }
    )
    svc = GuardianService(storage, cfg=cfg)
    try:
        result = await svc.google_drive_breach(
            resource_id="1AbC_dRiVeIdXyZ",
            breach_category="data_exposure",
            description="Public link overshared",
        )
        assert result["insurance_triggered"] is True
        assert result["asset_key"] == "gdrive/1AbC_dRiVeIdXyZ"
        assert result["purchase_id"] is not None
        assert result["skipped_reason"] is None
    finally:
        await svc.close()


@pytest.mark.asyncio
async def test_google_drive_breach_respects_cooldown(tmp_path) -> None:
    db_path = str(tmp_path / "guardian.sqlite")
    storage = Storage(db_path)
    await storage.init()

    cfg = settings.model_copy(
        update={
            "risk_threshold": 99.0,
            "cooldown_hours": 24,
            "drive_breach_synthetic_risk_score": 95.0,
            "enable_stability_penalty": False,
        }
    )
    svc = GuardianService(storage, cfg=cfg)
    try:
        r1 = await svc.google_drive_breach(resource_id="same-id", breach_category="unauthorized_access")
        assert r1["insurance_triggered"] is True

        r2 = await svc.google_drive_breach(resource_id="same-id", breach_category="other")
        assert r2["insurance_triggered"] is False
        assert r2["cooldown_applied"] is True
    finally:
        await svc.close()
