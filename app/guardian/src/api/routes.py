from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request
from pydantic import BaseModel, Field

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
from src.services.github_client import GitHubApiError
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
    try:
        result = await svc.scan_now(
            candidate_repos=candidate_repos,
            threshold=threshold,
            window_days=window_days,
        )
    except GitHubApiError as e:
        if e.status_code == 401:
            raise HTTPException(
                status_code=502,
                detail=(
                    "GitHub rejected the credentials (401). Fix or unset GITHUB_TOKEN: use a valid classic PAT "
                    '(Authorization: token) or a fine-grained PAT (starts with github_pat_; sent as Bearer), '
                    "or remove the token to scan public repos with lower rate limits."
                ),
            ) from e
        if e.status_code == 403:
            raise HTTPException(
                status_code=502,
                detail="GitHub API forbidden or rate limited (403). Wait or supply a token with higher limits.",
            ) from e
        raise HTTPException(status_code=502, detail=str(e)[:800]) from e

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



# ---------------------------------------------------------------------------
# Chat (Assistant tab — LLM proxy)
# ---------------------------------------------------------------------------
# Two upstream providers are supported:
#
#   * perplexity : OpenAI-compatible; needs PERPLEXITY_API_KEY. "sonar" models
#                  include web-grounded citations.
#   * llm7       : free, no API key, rate-limited. Default fallback.
#
# Provider selection is controlled by GUARDIAN_CHAT_PROVIDER:
#   "auto"       -> perplexity if key is set, else llm7
#   "perplexity" -> perplexity only (401 if key missing)
#   "llm7"       -> llm7 only
#
# On a transient perplexity failure (except 401), we fall back to llm7 so the
# chat tab stays functional.

LLM7_URL = "https://api.llm7.io/v1/chat/completions"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

# LLM7 free-tier aliases
_LLM7_DEFAULT_MODEL = "mistral-Nemo-Instruct-2407"
_LLM7_ALIASES: Dict[str, str] = {
    "mistral": "mistral-Nemo-Instruct-2407",
    "mistral-nemo": "mistral-Nemo-Instruct-2407",
    "gpt-oss": "gpt-oss:20b",
    "gpt-oss:20b": "gpt-oss:20b",
    "nemotron": "nemotron-3-nano:30b",
    "nemotron-3-nano:30b": "nemotron-3-nano:30b",
}

# Perplexity model aliases (frontend short name -> real model id)
_PERPLEXITY_DEFAULT_MODEL = "sonar"
_PERPLEXITY_ALIASES: Dict[str, str] = {
    "sonar": "sonar",
    "sonar-pro": "sonar-pro",
    "sonar-reasoning": "sonar-reasoning",
    "sonar-reasoning-pro": "sonar-reasoning-pro",
    "sonar-deep-research": "sonar-deep-research",
}


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=50)
    # Short alias (sonar / sonar-pro / mistral-nemo / ...). The backend
    # chooses the provider based on GUARDIAN_CHAT_PROVIDER and resolves the
    # alias to the real model id for that provider.
    model: str = "sonar"


class ChatResponse(BaseModel):
    model: str
    provider: str
    content: str


def _extract_content(data: Any) -> str:
    """
    Pull a usable string out of an OpenAI-style chat completion response.
    Falls back to `reasoning` / `reasoning_content` for reasoning models that
    leave `content` empty (e.g. gpt-oss, nemotron, sonar-reasoning).
    """
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices:
        return str(data.get("content") or "")

    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip()
    if content:
        return content

    reasoning = (msg.get("reasoning") or msg.get("reasoning_content") or "").strip()
    if reasoning:
        return reasoning

    delta = choices[0].get("delta") or {}
    return (delta.get("content") or "").strip()


def _append_citations(content: str, data: Any) -> str:
    """
    Perplexity returns a `citations` list (and some models embed [1][2] refs
    in the text). If citations exist and the content doesn't already contain a
    "Sources:" tail, append a compact source list.
    """
    if not isinstance(data, dict):
        return content
    citations = data.get("citations") or data.get("search_results") or []
    if not citations:
        return content
    if "Sources:" in content or "sources:" in content.lower():
        return content

    urls: List[str] = []
    for c in citations[:5]:
        if isinstance(c, str):
            urls.append(c)
        elif isinstance(c, dict):
            u = c.get("url")
            if isinstance(u, str):
                urls.append(u)
    if not urls:
        return content

    lines = ["", "", "Sources:"]
    for i, u in enumerate(urls, start=1):
        lines.append(f"{i}. {u}")
    return content + "\n".join(lines)


def _resolve_provider(model_alias: str) -> str:
    """
    Decide which upstream to use given config + the requested model alias.
    """
    cfg = (settings.guardian_chat_provider or "auto").strip().lower()
    has_pplx = bool((settings.perplexity_api_key or "").strip())

    if cfg == "perplexity":
        return "perplexity"
    if cfg == "llm7":
        return "llm7"

    # auto: route by alias if clear, else key presence
    if model_alias in _PERPLEXITY_ALIASES:
        return "perplexity" if has_pplx else "llm7"
    if model_alias in _LLM7_ALIASES:
        return "llm7"
    return "perplexity" if has_pplx else "llm7"


async def _call_perplexity(messages: List[Dict[str, str]], model_alias: str) -> ChatResponse:
    key = (settings.perplexity_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Perplexity selected but PERPLEXITY_API_KEY is not set.",
        )

    model = _PERPLEXITY_ALIASES.get(model_alias, _PERPLEXITY_DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0.4,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            PERPLEXITY_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "iarg-guardian/1.0",
            },
        )

    if resp.status_code >= 400:
        snippet = resp.text[:400] if resp.text else resp.reason_phrase
        if resp.status_code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail=f"Perplexity rejected credentials ({resp.status_code}). Check PERPLEXITY_API_KEY.",
            )
        if resp.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Perplexity rate limit exceeded. Try again shortly.",
            )
        raise HTTPException(
            status_code=502,
            detail=f"Perplexity returned {resp.status_code}: {snippet}",
        )

    try:
        data = resp.json()
    except Exception:
        data = {}

    content = _extract_content(data)
    if not content:
        raise HTTPException(status_code=502, detail="Empty response from Perplexity.")

    content = _append_citations(content, data)
    return ChatResponse(model=model, provider="perplexity", content=content)


async def _call_llm7(messages: List[Dict[str, str]], model_alias: str) -> ChatResponse:
    model = _LLM7_ALIASES.get(model_alias, _LLM7_DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            LLM7_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "iarg-guardian/1.0",
            },
        )

    if resp.status_code >= 400:
        snippet = resp.text[:400] if resp.text else resp.reason_phrase
        if resp.status_code == 429:
            try:
                info = resp.json().get("error", {})
                retry = info.get("retry_after")
                if retry:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Model is rate-limited. Retry in {retry}s.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass
        raise HTTPException(
            status_code=502,
            detail=f"LLM7 returned {resp.status_code}: {snippet}",
        )

    try:
        data = resp.json()
    except Exception:
        data = {}

    content = _extract_content(data)
    if not content:
        raise HTTPException(status_code=502, detail="Empty response from LLM7.")
    return ChatResponse(model=model, provider="llm7", content=content)


@router.get("/chat/providers")
async def chat_providers() -> Dict[str, Any]:
    """
    Report which chat providers are configured. The frontend uses this to
    decide which model list to render.
    """
    cfg = (settings.guardian_chat_provider or "auto").strip().lower()
    has_pplx = bool((settings.perplexity_api_key or "").strip())

    if cfg == "perplexity":
        active = "perplexity"
    elif cfg == "llm7":
        active = "llm7"
    else:
        active = "perplexity" if has_pplx else "llm7"

    return {
        "configured": cfg,
        "active": active,
        "perplexity_available": has_pplx,
        "models": {
            "perplexity": list(_PERPLEXITY_ALIASES.keys()) if has_pplx else [],
            "llm7": list({v: None for v in _LLM7_ALIASES.values()}.keys()),
        },
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    model_alias = (body.model or "").strip() or _PERPLEXITY_DEFAULT_MODEL
    messages = [m.model_dump() for m in body.messages]

    provider = _resolve_provider(model_alias)
    cfg = (settings.guardian_chat_provider or "auto").strip().lower()

    try:
        if provider == "perplexity":
            return await _call_perplexity(messages, model_alias)
        return await _call_llm7(messages, model_alias)
    except HTTPException as e:
        # Fall back to llm7 on transient perplexity failures, but not on auth
        # issues (user needs to see those).
        if (
            provider == "perplexity"
            and cfg == "auto"
            and e.status_code not in (401, 403, 429)
        ):
            # Pick a sensible llm7 model to retry with.
            return await _call_llm7(messages, "mistral-nemo")
        raise
    except httpx.HTTPError as e:
        if provider == "perplexity" and cfg == "auto":
            try:
                return await _call_llm7(messages, "mistral-nemo")
            except Exception:
                pass
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}") from e
