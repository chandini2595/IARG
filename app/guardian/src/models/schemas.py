from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RepoFullName(BaseModel):
    value: str


class RepoVisibility(str, Enum):
    public = "public"
    private = "private"


class RepoMetrics(BaseModel):
    repo_full_name: str
    visibility: RepoVisibility
    repo_size_kb: int
    last_pushed_at: Optional[datetime] = None

    commits_last_window: int
    open_prs: int
    open_issues: int


class RiskBreakdown(BaseModel):
    # Normalized factors (0..1)
    commits_norm: float = Field(ge=0.0, le=1.0)
    prs_norm: float = Field(ge=0.0, le=1.0)
    issues_norm: float = Field(ge=0.0, le=1.0)
    exposure_norm: float = Field(ge=0.0, le=1.0)
    stability_penalty: float = Field(ge=0.0, le=1.0)

    activity_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=100.0)

    # Contributions that explain "why"
    contributions: Dict[str, float] = Field(default_factory=dict)
    explanation: Dict[str, Any] = Field(default_factory=dict)


class RiskScoreResult(BaseModel):
    repo_full_name: str
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_level: RiskLevel
    breakdown: RiskBreakdown
    computed_at: datetime


class InsurancePolicyId(str, Enum):
    micro = "micro_policy"
    parametric = "parametric_policy"


class InsurancePolicyTemplate(BaseModel):
    policy_id: InsurancePolicyId
    name: str
    # Applies when risk_score is in [min_score, max_score] (max_score can be None for open-ended)
    min_score: float
    max_score: Optional[float]
    premium: float
    payout: float
    policy_type: str = "micro"  # for UI


class InsurancePurchase(BaseModel):
    purchase_id: UUID
    repo_full_name: str
    policy_id: InsurancePolicyId
    policy_name: str
    triggered_risk_score: float
    triggered_risk_level: RiskLevel
    premium: float
    payout: float
    status: str
    triggered_at: datetime


class InsuranceEvidence(BaseModel):
    evidence_id: UUID
    purchase_id: UUID
    evidence: Dict[str, Any]
    created_at: datetime


class PurchaseDetail(BaseModel):
    purchase: InsurancePurchase
    evidence: InsuranceEvidence


class ScanNowRequest(BaseModel):
    candidate_repos: Optional[List[str]] = None  # owner/repo
    threshold: Optional[float] = None
    window_days: Optional[int] = None


class ScanNowResponse(BaseModel):
    scanned_at: datetime
    selected_repo: str
    risk: RiskScoreResult
    insurance_triggered: bool
    purchase_id: Optional[UUID] = None
    cooldown_applied: bool = False
    skipped_reason: Optional[str] = None


class MonitorSummary(BaseModel):
    last_scan_at: Optional[datetime] = None
    selected_repo: Optional[str] = None
    latest_risk_score: Optional[float] = None
    latest_risk_level: Optional[RiskLevel] = None


class RiskLatestResponse(BaseModel):
    last_scan_at: Optional[datetime] = None
    selected_repo: Optional[str] = None
    latest_risk: Optional[RiskScoreResult] = None


class PurchasesListResponse(BaseModel):
    purchases: List[InsurancePurchase]


class GoogleDriveBreachRequest(BaseModel):
    """Report a Google Drive data or security incident for a monitored resource."""

    resource_id: str = Field(..., min_length=1, description="Drive file or folder ID")
    breach_category: str = Field(
        ...,
        min_length=1,
        description="e.g. data_exposure, unauthorized_access, ransomware, malware, other",
    )
    description: Optional[str] = None


class GoogleDriveBreachResponse(BaseModel):
    triggered_at: datetime
    asset_key: str
    insurance_triggered: bool
    purchase_id: Optional[UUID] = None
    cooldown_applied: bool = False
    skipped_reason: Optional[str] = None

