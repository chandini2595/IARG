"""
API routes for the risk scoring service
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, List, Optional, Any
import asyncio

from src.models.asset import (
    RiskScoreRequest, RiskScoreResponse,
    BatchRiskScoreRequest, BatchRiskScoreResponse,
    RiskScore, RiskLevel
)
from src.services.risk_scorer import RiskScoringService
from src.services.neo4j_service import Neo4jService
from src.services.redis_service import RedisService
from src.utils.logging import get_logger

# Global service instances (will be injected)
risk_scorer: Optional[RiskScoringService] = None
neo4j_service: Optional[Neo4jService] = None
redis_service: Optional[RedisService] = None

logger = get_logger(__name__)
router = APIRouter()


def get_risk_scorer() -> RiskScoringService:
    """Dependency to get risk scorer service"""
    if not risk_scorer:
        raise HTTPException(status_code=503, detail="Risk scoring service not available")
    return risk_scorer


def get_neo4j_service() -> Neo4jService:
    """Dependency to get Neo4j service"""
    if not neo4j_service:
        raise HTTPException(status_code=503, detail="Neo4j service not available")
    return neo4j_service


def get_redis_service() -> RedisService:
    """Dependency to get Redis service"""
    if not redis_service:
        raise HTTPException(status_code=503, detail="Redis service not available")
    return redis_service


@router.post("/score", response_model=RiskScoreResponse)
async def score_asset(
    request: RiskScoreRequest,
    scorer: RiskScoringService = Depends(get_risk_scorer)
) -> RiskScoreResponse:
    """Score a single asset"""
    try:
        logger.info(f"Scoring asset {request.asset_id}")
        response = await scorer.score_asset(request)
        
        if response.success:
            logger.info(f"Asset {request.asset_id} scored successfully: {response.risk_score.overall_score}")
        else:
            logger.error(f"Failed to score asset {request.asset_id}: {response.error}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error scoring asset {request.asset_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/score/batch", response_model=BatchRiskScoreResponse)
async def score_assets_batch(
    request: BatchRiskScoreRequest,
    scorer: RiskScoringService = Depends(get_risk_scorer)
) -> BatchRiskScoreResponse:
    """Score multiple assets in batch"""
    try:
        logger.info(f"Batch scoring {len(request.asset_ids)} assets")
        response = await scorer.score_assets_batch(request)
        
        logger.info(f"Batch scoring completed: {len(response.risk_scores)} successful, "
                   f"{len(response.failed_assets)} failed")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in batch scoring: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/score/{asset_id}", response_model=RiskScoreResponse)
async def get_asset_risk_score(
    asset_id: str,
    force_refresh: bool = False,
    include_explanation: bool = True,
    scorer: RiskScoringService = Depends(get_risk_scorer)
) -> RiskScoreResponse:
    """Get risk score for a specific asset"""
    try:
        request = RiskScoreRequest(
            asset_id=asset_id,
            force_refresh=force_refresh,
            include_explanation=include_explanation
        )
        
        return await scorer.score_asset(request)
        
    except Exception as e:
        logger.error(f"Error getting risk score for asset {asset_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/assets/high-risk")
async def get_high_risk_assets(
    threshold: float = 70.0,
    limit: int = 50,
    neo4j: Neo4jService = Depends(get_neo4j_service)
) -> Dict[str, Any]:
    """Get assets with high risk scores"""
    try:
        assets = await neo4j.get_high_risk_assets(threshold, limit)
        
        return {
            "success": True,
            "threshold": threshold,
            "count": len(assets),
            "assets": assets
        }
        
    except Exception as e:
        logger.error(f"Error getting high-risk assets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/assets/{asset_id}/dependencies")
async def get_asset_dependencies(
    asset_id: str,
    neo4j: Neo4jService = Depends(get_neo4j_service)
) -> Dict[str, Any]:
    """Get asset dependencies and dependents"""
    try:
        dependency_count = await neo4j.get_dependency_count(asset_id)
        dependent_count = await neo4j.get_dependent_count(asset_id)
        lineage = await neo4j.get_asset_lineage(asset_id)
        
        return {
            "success": True,
            "asset_id": asset_id,
            "dependency_count": dependency_count,
            "dependent_count": dependent_count,
            "lineage": lineage
        }
        
    except Exception as e:
        logger.error(f"Error getting dependencies for asset {asset_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/model/info")
async def get_model_info(
    scorer: RiskScoringService = Depends(get_risk_scorer)
) -> Dict[str, Any]:
    """Get information about the risk scoring model"""
    try:
        model = scorer.ml_model
        
        return {
            "success": True,
            "model_version": model.model_version,
            "is_trained": model.is_trained,
            "feature_count": len(model.feature_names),
            "feature_names": model.feature_names,
            "training_stats": model.training_stats,
            "model_params": model.xgb_params
        }
        
    except Exception as e:
        logger.error(f"Error getting model info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/model/feature-importance")
async def get_feature_importance(
    scorer: RiskScoringService = Depends(get_risk_scorer),
    redis: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """Get feature importance from the model"""
    try:
        model = scorer.ml_model
        
        if not model.is_trained:
            raise HTTPException(status_code=400, detail="Model is not trained")
        
        # Try to get from cache first
        cached_importance = await redis.get_feature_importance(model.model_version)
        if cached_importance:
            return {
                "success": True,
                "model_version": model.model_version,
                "feature_importance": cached_importance,
                "cached": True
            }
        
        # Get from model
        feature_importance = model._get_feature_importance()
        
        # Cache the result
        await redis.store_feature_importance(model.model_version, feature_importance)
        
        return {
            "success": True,
            "model_version": model.model_version,
            "feature_importance": feature_importance,
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"Error getting feature importance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/model/retrain")
async def retrain_model(
    background_tasks: BackgroundTasks,
    scorer: RiskScoringService = Depends(get_risk_scorer)
) -> Dict[str, Any]:
    """Trigger model retraining"""
    try:
        # Add retraining task to background
        background_tasks.add_task(_retrain_model_background, scorer)
        
        return {
            "success": True,
            "message": "Model retraining started in background"
        }
        
    except Exception as e:
        logger.error(f"Error starting model retraining: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def _retrain_model_background(scorer: RiskScoringService) -> None:
    """Background task for model retraining"""
    try:
        logger.info("Starting background model retraining")
        updated = await scorer.update_model_if_needed()
        
        if updated:
            logger.info("Model retrained successfully")
        else:
            logger.info("Model retraining not needed")
            
    except Exception as e:
        logger.error(f"Error in background model retraining: {str(e)}")


@router.get("/statistics")
async def get_statistics(
    neo4j: Neo4jService = Depends(get_neo4j_service),
    redis: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """Get risk scoring statistics"""
    try:
        # Get asset statistics from Neo4j
        asset_stats = await neo4j.get_asset_statistics()
        
        # Get cache statistics from Redis
        cache_stats = await redis.get_cache_statistics()
        
        return {
            "success": True,
            "timestamp": asyncio.get_event_loop().time(),
            "asset_statistics": asset_stats,
            "cache_statistics": cache_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/risk-levels")
async def get_risk_level_distribution(
    neo4j: Neo4jService = Depends(get_neo4j_service)
) -> Dict[str, Any]:
    """Get distribution of risk levels across assets"""
    try:
        stats = await neo4j.get_asset_statistics()
        
        total_assets = stats.get('total_assets', 0)
        high_risk = stats.get('high_risk_count', 0)
        medium_risk = stats.get('medium_risk_count', 0)
        low_risk = stats.get('low_risk_count', 0)
        
        return {
            "success": True,
            "total_assets": total_assets,
            "distribution": {
                "high": {
                    "count": high_risk,
                    "percentage": (high_risk / total_assets * 100) if total_assets > 0 else 0
                },
                "medium": {
                    "count": medium_risk,
                    "percentage": (medium_risk / total_assets * 100) if total_assets > 0 else 0
                },
                "low": {
                    "count": low_risk,
                    "percentage": (low_risk / total_assets * 100) if total_assets > 0 else 0
                }
            },
            "average_risk_score": stats.get('avg_risk_score', 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting risk level distribution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/webhook/asset-event")
async def handle_asset_event(
    event: Dict[str, Any],
    background_tasks: BackgroundTasks,
    scorer: RiskScoringService = Depends(get_risk_scorer)
) -> Dict[str, Any]:
    """Handle asset events from webhooks"""
    try:
        # Process event in background
        background_tasks.add_task(scorer.process_event, event)
        
        return {
            "success": True,
            "message": "Event queued for processing",
            "event_type": event.get('type', 'unknown')
        }
        
    except Exception as e:
        logger.error(f"Error handling asset event: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Set global service instances (called from main.py)
def set_services(scorer_service: RiskScoringService, 
                neo4j_svc: Neo4jService, 
                redis_svc: RedisService) -> None:
    """Set global service instances"""
    global risk_scorer, neo4j_service, redis_service
    risk_scorer = scorer_service
    neo4j_service = neo4j_svc
    redis_service = redis_svc