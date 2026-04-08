from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from src.config import Settings, settings
from src.models.schemas import InsurancePolicyId, InsurancePolicyTemplate, RiskLevel
from src.services.storage import Storage


@dataclass(frozen=True)
class CoolingDecision:
    allowed: bool
    cooldown_applied: bool
    reason: Optional[str] = None


class InsuranceEngine:
    def __init__(self, storage: Storage, cfg: Settings = settings):
        self.storage = storage
        self.cfg = cfg

        self.policies = [
            InsurancePolicyTemplate(
                policy_id=InsurancePolicyId.micro,
                name="Micro Policy (High Risk)",
                min_score=60.0,
                max_score=79.999,
                premium=1500.0,
                payout=20000.0,
                policy_type="micro",
            ),
            InsurancePolicyTemplate(
                policy_id=InsurancePolicyId.parametric,
                name="Parametric Policy (Critical Risk)",
                min_score=80.0,
                max_score=None,
                premium=5000.0,
                payout=100000.0,
                policy_type="parametric",
            ),
        ]

    def select_policy(self, risk_score: float, risk_level: RiskLevel) -> Optional[InsurancePolicyTemplate]:
        # Prefer explicit score ranges to keep it transparent.
        for p in self.policies:
            if risk_score < p.min_score:
                continue
            if p.max_score is None or risk_score <= p.max_score:
                return p
        return None

    def evaluate_cooldown(self, *, last_purchase_at: Optional[datetime], now: datetime) -> CoolingDecision:
        if not last_purchase_at:
            return CoolingDecision(allowed=True, cooldown_applied=False)

        cooldown_delta = now - last_purchase_at
        if cooldown_delta.total_seconds() < self.cfg.cooldown_hours * 3600:
            return CoolingDecision(
                allowed=False,
                cooldown_applied=True,
                reason=f"Cooldown active: last purchase {cooldown_delta.total_seconds() / 3600:.1f}h ago.",
            )
        return CoolingDecision(allowed=True, cooldown_applied=False)

    async def plan_purchase(
        self,
        *,
        repo_full_name: str,
        risk_score: float,
        risk_level: RiskLevel,
        now: datetime,
        threshold: Optional[float] = None,
        ignore_threshold: bool = False,
    ) -> Dict[str, object]:
        """
        Decide whether a purchase should be triggered without collecting evidence yet.

        When ``ignore_threshold`` is True (e.g. confirmed external breach), the risk threshold
        check is skipped; cooldown and policy-band matching still apply.
        """
        effective_threshold = self.cfg.risk_threshold if threshold is None else float(threshold)

        if not ignore_threshold and risk_score <= effective_threshold:
            return {"allowed": False, "triggered": False, "cooldown_applied": False, "reason": "below_threshold"}

        policy = self.select_policy(risk_score, risk_level)
        if policy is None:
            return {"allowed": False, "triggered": False, "cooldown_applied": False, "reason": "no_policy_match"}

        last = await self.storage.get_last_purchase_for_repo(repo_full_name)
        last_purchase_at: Optional[datetime] = None
        if last and last.get("triggered_at"):
            last_purchase_at = datetime.fromisoformat(last["triggered_at"])

        decision = self.evaluate_cooldown(last_purchase_at=last_purchase_at, now=now)
        if not decision.allowed:
            return {
                "allowed": False,
                "triggered": False,
                "cooldown_applied": True,
                "reason": decision.reason,
                "policy_id": policy.policy_id.value,
                "policy_name": policy.name,
                "premium": policy.premium,
                "payout": policy.payout,
            }

        return {
            "allowed": True,
            "triggered": True,
            "cooldown_applied": False,
            "reason": None,
            "policy_id": policy.policy_id.value,
            "policy_name": policy.name,
            "premium": policy.premium,
            "payout": policy.payout,
        }

    async def maybe_trigger_purchase(
        self,
        *,
        repo_full_name: str,
        risk_score: float,
        risk_level: RiskLevel,
        triggered_at: datetime,
        evidence: Dict,
        ignore_threshold: bool = False,
    ) -> Dict[str, object]:
        """
        Trigger a policy purchase if:
        - risk_score > threshold (unless ignore_threshold)
        - cooldown allows
        """
        plan = await self.plan_purchase(
            repo_full_name=repo_full_name,
            risk_score=risk_score,
            risk_level=risk_level,
            now=triggered_at,
            threshold=None,
            ignore_threshold=ignore_threshold,
        )

        if not plan.get("allowed"):
            return {
                "triggered": False,
                "purchase_id": None,
                "cooldown_applied": bool(plan.get("cooldown_applied", False)),
                "reason": plan.get("reason"),
            }

        created = await self.storage.create_purchase_with_evidence(
            repo_full_name=repo_full_name,
            policy_id=str(plan["policy_id"]),
            policy_name=str(plan["policy_name"]),
            triggered_risk_score=risk_score,
            triggered_risk_level=risk_level.value,
            premium=float(plan["premium"]),
            payout=float(plan["payout"]),
            triggered_at=triggered_at,
            evidence=evidence,
        )

        return {
            "triggered": True,
            "purchase_id": created["purchase_id"],
            "cooldown_applied": False,
            "policy_id": str(plan["policy_id"]),
            "policy_name": str(plan["policy_name"]),
            "premium": float(plan["premium"]),
            "payout": float(plan["payout"]),
        }

