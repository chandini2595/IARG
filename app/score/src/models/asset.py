"""
Asset data models for risk scoring
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class AssetType(str, Enum):
    """Asset type enumeration"""
    REPOSITORY = "repository"
    MODEL = "model"
    DATASET = "dataset"
    DOCUMENT = "document"
    CODE = "code"
    API = "api"


class AssetSource(str, Enum):
    """Asset source enumeration"""
    GITHUB = "github"
    HUGGINGFACE = "huggingface"
    SNOWFLAKE = "snowflake"
    GOOGLE_DRIVE = "google_drive"


class RiskLevel(str, Enum):
    """Risk level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Asset(BaseModel):
    """Asset model for risk scoring"""
    id: str
    type: AssetType
    name: str
    owner: str
    source: AssetSource
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_accessed: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    status: str = "active"


class RiskFactors(BaseModel):
    """Risk factors for an asset"""
    exposure: float = Field(ge=0, le=1, description="External exposure level")
    sensitivity: float = Field(ge=0, le=1, description="Data sensitivity level")
    criticality: float = Field(ge=0, le=1, description="Business criticality")
    vulnerability: float = Field(ge=0, le=1, description="Technical vulnerability")
    access_frequency: float = Field(ge=0, description="Access frequency score")
    dependency_count: int = Field(ge=0, description="Number of dependencies")
    age_days: int = Field(ge=0, description="Asset age in days")
    size_mb: float = Field(ge=0, description="Asset size in MB")


class ThreatIntelligence(BaseModel):
    """Threat intelligence data"""
    cve_count: int = Field(ge=0, description="Number of CVEs")
    severity_score: float = Field(ge=0, le=10, description="CVSS severity score")
    exploit_available: bool = Field(description="Exploit availability")
    threat_actors: List[str] = Field(default_factory=list)
    last_updated: datetime


class AISpecificRisks(BaseModel):
    """AI/ML specific risk factors"""
    model_inversion_risk: float = Field(ge=0, le=1, description="Model inversion attack risk")
    membership_inference_risk: float = Field(ge=0, le=1, description="Membership inference risk")
    data_poisoning_risk: float = Field(ge=0, le=1, description="Data poisoning risk")
    adversarial_attack_risk: float = Field(ge=0, le=1, description="Adversarial attack risk")
    privacy_leakage_risk: float = Field(ge=0, le=1, description="Privacy leakage risk")


class RiskScore(BaseModel):
    """Risk score result"""
    asset_id: str
    overall_score: float = Field(ge=0, le=100, description="Overall risk score")
    risk_level: RiskLevel
    component_scores: Dict[str, float] = Field(description="Individual component scores")
    confidence: float = Field(ge=0, le=1, description="Prediction confidence")
    factors: RiskFactors
    threat_intel: Optional[ThreatIntelligence] = None
    ai_risks: Optional[AISpecificRisks] = None
    timestamp: datetime
    model_version: str
    explanation: Dict[str, Any] = Field(default_factory=dict)


class RiskScoreRequest(BaseModel):
    """Request for risk scoring"""
    asset_id: str
    force_refresh: bool = False
    include_explanation: bool = True


class RiskScoreResponse(BaseModel):
    """Response for risk scoring"""
    success: bool
    risk_score: Optional[RiskScore] = None
    error: Optional[str] = None
    cached: bool = False


class BatchRiskScoreRequest(BaseModel):
    """Batch risk scoring request"""
    asset_ids: List[str]
    force_refresh: bool = False
    include_explanation: bool = True


class BatchRiskScoreResponse(BaseModel):
    """Batch risk scoring response"""
    success: bool
    risk_scores: List[RiskScore] = Field(default_factory=list)
    failed_assets: List[str] = Field(default_factory=list)
    errors: Dict[str, str] = Field(default_factory=dict)