from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.config import Settings, settings
from src.models.schemas import RiskBreakdown, RiskLevel, RiskScoreResult, RepoVisibility


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def normalize_ratio(count: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return clamp(count / max_value, 0.0, 1.0)


def exposure_proxy_norm(
    *,
    visibility: RepoVisibility,
    repo_size_kb: int,
    cfg: Settings,
) -> float:
    visibility_norm = 1.0 if visibility == RepoVisibility.public else 0.4
    size_norm = normalize_ratio(float(repo_size_kb), float(cfg.max_repo_size_kb_for_norm))
    return clamp(cfg.exposure_public_weight * visibility_norm + cfg.exposure_size_weight * size_norm, 0.0, 1.0)


def stability_penalty_norm(*, last_pushed_at: Optional[datetime], cfg: Settings) -> float:
    if not cfg.enable_stability_penalty:
        return 0.0
    if not last_pushed_at:
        # If we don't know, be conservative.
        return 0.5
    days_since_push = (datetime.utcnow() - last_pushed_at).days
    # Map stale to (0..1): 0 at "fresh", 1 at "very stale".
    if days_since_push <= cfg.stale_days_threshold:
        return 0.2
    # Past threshold grows linearly to 1 at ~2x threshold.
    upper = max(cfg.stale_days_threshold * 2, cfg.stale_days_threshold + 1)
    return clamp((days_since_push - cfg.stale_days_threshold) / (upper - cfg.stale_days_threshold), 0.0, 1.0)


def compute_risk_level(risk_score: float) -> RiskLevel:
    if risk_score >= 80:
        return RiskLevel.critical
    if risk_score >= 60:
        return RiskLevel.high
    if risk_score >= 30:
        return RiskLevel.medium
    return RiskLevel.low


_xgb_model = None


def _extract_risk_features(
    *,
    commits_last_window: int,
    open_prs: int,
    open_issues: int,
    visibility: RepoVisibility,
    repo_size_kb: int,
    last_pushed_at: Optional[datetime],
    cfg: Settings,
) -> List[float]:
    """
    Feature vector used by the risk model (and the teacher heuristic).
    Order:
      [commits_norm, prs_norm, issues_norm, exposure_norm, stability_penalty_norm]
    """
    commits_norm = normalize_ratio(commits_last_window, cfg.max_commits_for_norm)
    prs_norm = normalize_ratio(open_prs, cfg.max_open_prs_for_norm)
    issues_norm = normalize_ratio(open_issues, cfg.max_open_issues_for_norm)
    exposure_norm = exposure_proxy_norm(
        visibility=visibility,
        repo_size_kb=repo_size_kb,
        cfg=cfg,
    )
    stability = stability_penalty_norm(last_pushed_at=last_pushed_at, cfg=cfg)
    return [commits_norm, prs_norm, issues_norm, exposure_norm, stability]


def _teacher_risk_score_from_features(features: List[float]) -> float:
    """
    Teacher heuristic mapping for synthetic/demo training.
    Inputs are already normalized in [0..1].
    """
    commits_norm, prs_norm, issues_norm, exposure_norm, stability = features
    activity = 0.50 * commits_norm + 0.30 * prs_norm + 0.20 * issues_norm
    risk_score = clamp(100.0 * (0.65 * activity + 0.25 * exposure_norm + 0.10 * stability), 0.0, 100.0)
    return risk_score


def _get_xgb_model(cfg: Settings):
    """
    Demo-only XGBoost model loader/trainer.

    With no real labels in this project, we train XGBoost to mimic
    the current heuristic using synthetic features.
    """
    global _xgb_model
    if _xgb_model is not None:
        return _xgb_model

    try:
        from xgboost import XGBRegressor
        import numpy as np
    except Exception:
        return None

    # Train synthetic teacher-distillation model.
    samples = int(cfg.xgb_demo_samples)
    if samples <= 0:
        return None

    rng = np.random.default_rng(seed=42)
    X = rng.uniform(0.0, 1.0, size=(samples, 5))
    y = np.array([_teacher_risk_score_from_features(row.tolist()) for row in X], dtype=float)

    model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
    )
    model.fit(X, y)
    _xgb_model = model
    return _xgb_model


def compute_risk_score(
    *,
    repo_full_name: str,
    commits_last_window: int,
    open_prs: int,
    open_issues: int,
    visibility: RepoVisibility,
    repo_size_kb: int,
    last_pushed_at: Optional[datetime] = None,
    cfg: Settings = settings,
    now: Optional[datetime] = None,
) -> RiskScoreResult:
    """
    Explainable risk scoring (MVP).

    Uses a weighted model over normalized GitHub activity metrics.
    """
    if now is None:
        now = datetime.utcnow()

    # Teacher-computed normalized features (also used as model inputs)
    features = _extract_risk_features(
        commits_last_window=commits_last_window,
        open_prs=open_prs,
        open_issues=open_issues,
        visibility=visibility,
        repo_size_kb=repo_size_kb,
        last_pushed_at=last_pushed_at,
        cfg=cfg,
    )
    commits_norm, prs_norm, issues_norm, exposure_norm, stability = features

    if cfg.risk_model_type == "xgb-demo":
        model = _get_xgb_model(cfg)
        if model is not None:
            # XGBoost expects a 2D array
            import numpy as np

            X = np.array([features], dtype=float)
            pred = float(model.predict(X)[0])
            risk_score = clamp(pred, 0.0, 100.0)
        else:
            # If xgboost isn't available for some reason, fallback to heuristic.
            activity = 0.50 * commits_norm + 0.30 * prs_norm + 0.20 * issues_norm
            risk_score = clamp(100.0 * (0.65 * activity + 0.25 * exposure_norm + 0.10 * stability), 0.0, 100.0)
    else:
        # Default: current rule-based scoring
        activity = 0.50 * commits_norm + 0.30 * prs_norm + 0.20 * issues_norm
        risk_score = clamp(100.0 * (0.65 * activity + 0.25 * exposure_norm + 0.10 * stability), 0.0, 100.0)

    # activity is a convex combination in normalized space (for breakdown/contributions)
    activity = 0.50 * commits_norm + 0.30 * prs_norm + 0.20 * issues_norm

    risk_level = compute_risk_level(risk_score)

    # "Contributions" in score space (sum not necessarily 100 due to clamp).
    contributions = {
        "activity_weighted": round(100.0 * (0.65 * activity / 1.0), 4),
        "exposure_weighted": round(100.0 * (0.25 * exposure_norm / 1.0), 4),
        "stability_weighted": round(100.0 * (0.10 * stability / 1.0), 4),
    }

    breakdown = RiskBreakdown(
        commits_norm=commits_norm,
        prs_norm=prs_norm,
        issues_norm=issues_norm,
        exposure_norm=exposure_norm,
        stability_penalty=stability,
        activity_score=clamp(activity, 0.0, 1.0),
        risk_score=risk_score,
        contributions=contributions,
        explanation={
            "activity_formula": "activity=0.50*C+0.30*P+0.20*I (normalized)",
            "risk_formula": "risk=100*(0.65*activity+0.25*exposure+0.10*stability) (clamped 0..100)",
            "C_commits_norm": commits_norm,
            "P_prs_norm": prs_norm,
            "I_issues_norm": issues_norm,
            "exposure_visibility_norm": 1.0 if visibility == RepoVisibility.public else 0.4,
            "exposure_size_norm": normalize_ratio(float(repo_size_kb), float(cfg.max_repo_size_kb_for_norm)),
            "stability_enabled": cfg.enable_stability_penalty,
            "risk_model_type": cfg.risk_model_type,
            "xgb_demo_note": "If risk_model_type=xgb-demo, XGBoost is trained to mimic the heuristic on synthetic teacher data (no real labels).",
        },
    )

    return RiskScoreResult(
        repo_full_name=repo_full_name,
        risk_score=risk_score,
        risk_level=risk_level,
        breakdown=breakdown,
        computed_at=now,
    )


def compute_activity_score_for_selection(
    *,
    commits_last_window: int,
    open_prs: int,
    open_issues: int,
    cfg: Settings = settings,
) -> float:
    commits_norm = normalize_ratio(commits_last_window, cfg.max_commits_for_norm)
    prs_norm = normalize_ratio(open_prs, cfg.max_open_prs_for_norm)
    issues_norm = normalize_ratio(open_issues, cfg.max_open_issues_for_norm)
    return clamp(0.50 * commits_norm + 0.30 * prs_norm + 0.20 * issues_norm, 0.0, 1.0)

