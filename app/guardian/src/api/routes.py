from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request

from src.config import settings
from src.models.schemas import (
    GoogleDriveBreachRequest,
    GoogleDriveBreachResponse,
    InsuranceEvidence,
    InsurancePurchase,
    MonitorSummary,
    PurchaseDetail,
    RiskLatestResponse,
    ScanNowRequest,
    ScanNowResponse,
)
from src.services.drive_monitor_service import DriveMonitorService
from src.services.guardian_service import GuardianService
from src.services.storage import Storage


router = APIRouter(prefix="/api/guardian", tags=["guardian"])


def get_storage(request) -> Storage:
    storage = getattr(request.app.state, "storage", None)
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return storage


def get_guardian_service(request) -> GuardianService:
    svc = getattr(request.app.state, "guardian_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="Guardian service not initialized")
    return svc


def get_drive_monitor(request: Request) -> DriveMonitorService:
    mon = getattr(request.app.state, "drive_monitor", None)
    if not mon:
        raise HTTPException(status_code=503, detail="Drive monitor not initialized")
    return mon


def _require_drive_breach_secret(request: Request) -> None:
    expected = (settings.drive_breach_webhook_secret or "").strip()
    if not expected:
        return
    got = request.headers.get("X-IARG-Drive-Breach-Secret", "")
    if got != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-IARG-Drive-Breach-Secret")


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "healthy", "service": "iarg-guardian", "version": "1.0.0"}


@router.post("/scan/now", response_model=ScanNowResponse)
async def scan_now(
    request: Request,
    body: ScanNowRequest,
) -> Any:
    # Dependencies via app.state (we avoid extra wiring).
    candidate_repos = body.candidate_repos or settings.github_repos_list
    if not candidate_repos:
        raise HTTPException(status_code=400, detail="No candidate repos configured (set GITHUB_REPOS)")

    threshold = float(body.threshold) if body.threshold is not None else float(settings.risk_threshold)
    window_days = int(body.window_days) if body.window_days is not None else int(settings.scan_window_days)

    svc = get_guardian_service(request)
    result = await svc.scan_now(
        candidate_repos=candidate_repos,
        threshold=threshold,
        window_days=window_days,
    )

    risk = result["risk"]

    return ScanNowResponse(
        scanned_at=result["scanned_at"],
        selected_repo=result["selected_repo"],
        risk=risk,
        insurance_triggered=result["insurance_triggered"],
        purchase_id=result.get("purchase_id"),
        cooldown_applied=result.get("cooldown_applied", False),
        skipped_reason=result.get("skipped_reason"),
    )


@router.post("/google-drive/breach", response_model=GoogleDriveBreachResponse)
async def google_drive_breach(
    request: Request,
    body: GoogleDriveBreachRequest,
) -> GoogleDriveBreachResponse:
    """
    Report a Google Drive security or data incident. Insurance is evaluated immediately
    with a critical synthetic risk score; the normal GitHub activity threshold is bypassed.
    Production use: wire Google Workspace alert center, DLP, or Cloud Pub/Sub to this endpoint.
    """
    _require_drive_breach_secret(request)
    svc = get_guardian_service(request)
    try:
        result = await svc.google_drive_breach(
            resource_id=body.resource_id,
            breach_category=body.breach_category,
            description=body.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return GoogleDriveBreachResponse(
        triggered_at=result["triggered_at"],
        asset_key=result["asset_key"],
        insurance_triggered=result["insurance_triggered"],
        purchase_id=result.get("purchase_id"),
        cooldown_applied=result.get("cooldown_applied", False),
        skipped_reason=result.get("skipped_reason"),
    )


@router.get("/google-drive/monitor/status")
async def google_drive_monitor_status(request: Request) -> Dict[str, Any]:
    mon = get_drive_monitor(request)
    storage = get_storage(request)
    meta = await storage.get_drive_monitor_meta()
    return {
        "monitor_enabled": bool(settings.google_drive_monitor_enabled),
        "oauth_configured": mon.is_configured(),
        "monitored_resource_ids": settings.google_drive_monitored_ids_list,
        "poll_interval_seconds": int(settings.google_drive_poll_interval_seconds),
        "folder_max_children": int(settings.google_drive_folder_max_children),
        "allowed_email_domains": sorted(settings.google_drive_allowed_email_domains_set),
        "flag_domain_shares": bool(settings.google_drive_flag_domain_shares),
        "last_poll_at": meta.get("last_poll_at"),
        "last_poll_ok": meta.get("last_poll_ok"),
        "last_error": meta.get("last_error"),
        "detection_rules": {
            "new_anyone_permission": "Triggers data_exposure (public / anyone-with-link style share).",
            "new_domain_permission": "Triggers only if GOOGLE_DRIVE_FLAG_DOMAIN_SHARES=true (and optional domain allowlist logic).",
            "new_user_outside_domains": "Triggers if GOOGLE_DRIVE_ALLOWED_EMAIL_DOMAINS is non-empty and the invitee email domain is not listed.",
            "baseline": "First successful ACL snapshot per resource does not trigger insurance.",
        },
    }


@router.post("/google-drive/monitor/poll-now")
async def google_drive_monitor_poll_now(request: Request) -> Dict[str, Any]:
    """Run one Drive ACL poll immediately (same logic as the background task)."""
    _require_drive_breach_secret(request)
    mon = get_drive_monitor(request)
    return await mon.poll_once()


@router.get("/monitor/summary", response_model=MonitorSummary)
async def monitor_summary(request: Request) -> MonitorSummary:
    storage: Storage = get_storage(request)
    summary = await storage.get_monitor_summary()
    if not summary:
        return MonitorSummary()

    last_scan_at = summary.get("last_scan_at")
    latest_score = summary.get("latest_risk_score")
    latest_level = summary.get("latest_risk_level")
    latest_risk_json = summary.get("latest_risk_json")

    parsed_last = datetime.fromisoformat(last_scan_at) if last_scan_at else None

    return MonitorSummary(
        last_scan_at=parsed_last,
        selected_repo=summary.get("selected_repo"),
        latest_risk_score=latest_score,
        latest_risk_level=latest_level,
    )


@router.get("/risk/latest", response_model=RiskLatestResponse)
async def risk_latest(request: Request) -> RiskLatestResponse:
    storage: Storage = get_storage(request)
    summary = await storage.get_monitor_summary()
    if not summary:
        return RiskLatestResponse()

    last_scan_at = summary.get("last_scan_at")
    selected_repo = summary.get("selected_repo")
    latest_risk_json = summary.get("latest_risk_json")
    latest_risk = None
    if latest_risk_json:
        latest_risk = json.loads(latest_risk_json)

    parsed_last = datetime.fromisoformat(last_scan_at) if last_scan_at else None

    return RiskLatestResponse(
        last_scan_at=parsed_last,
        selected_repo=selected_repo,
        latest_risk=latest_risk,
    )


@router.get("/insurance/purchases")
async def purchases_list(
    request: Request,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    storage: Storage = get_storage(request)
    rows = await storage.list_purchases(limit=limit, offset=offset)
    # Evidence not included in list endpoint.
    purchases = []
    for r in rows:
        purchases.append(
            InsurancePurchase(
                purchase_id=r["purchase_id"],
                repo_full_name=r["repo_full_name"],
                policy_id=r["policy_id"],
                policy_name=r["policy_name"],
                triggered_risk_score=r["triggered_risk_score"],
                triggered_risk_level=r["triggered_risk_level"],
                premium=r["premium"],
                payout=r["payout"],
                status=r["status"],
                triggered_at=datetime.fromisoformat(r["triggered_at"]),
            )
        )
    return {"purchases": purchases}


@router.get("/insurance/purchases/{purchase_id}", response_model=PurchaseDetail)
async def purchase_detail(request: Request, purchase_id: str) -> PurchaseDetail:
    storage: Storage = get_storage(request)
    detail = await storage.get_purchase_detail(purchase_id=purchase_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Purchase not found")
    purchase_row, evidence_row = detail

    purchase = InsurancePurchase(
        purchase_id=purchase_row["purchase_id"],
        repo_full_name=purchase_row["repo_full_name"],
        policy_id=purchase_row["policy_id"],
        policy_name=purchase_row["policy_name"],
        triggered_risk_score=purchase_row["triggered_risk_score"],
        triggered_risk_level=purchase_row["triggered_risk_level"],
        premium=purchase_row["premium"],
        payout=purchase_row["payout"],
        status=purchase_row["status"],
        triggered_at=datetime.fromisoformat(purchase_row["triggered_at"]),
    )

    evidence = InsuranceEvidence(
        evidence_id=evidence_row["evidence_id"],
        purchase_id=evidence_row["purchase_id"],
        evidence=json.loads(evidence_row["evidence_json"]),
        created_at=datetime.fromisoformat(evidence_row["created_at"]),
    )

    return PurchaseDetail(purchase=purchase, evidence=evidence)

