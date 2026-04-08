"""
Main risk scoring service that orchestrates feature engineering and ML models
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from src.models.asset import (
    Asset, RiskFactors, ThreatIntelligence, AISpecificRisks,
    RiskScore, RiskLevel, RiskScoreRequest, RiskScoreResponse,
    BatchRiskScoreRequest, BatchRiskScoreResponse
)
from src.services.feature_engineering import FeatureEngineer
from src.services.ml_models import RiskScoringModel, SyntheticDataGenerator
from src.services.neo4j_service import Neo4jService
from src.services.redis_service import RedisService
from src.services.threat_intelligence import ThreatIntelligenceService
from src.utils.logging import LoggerMixin
from src.config import settings


class RiskScoringService(LoggerMixin):
    """Main risk scoring service"""
    
    def __init__(self, neo4j_service: Neo4jService, redis_service: RedisService):
        self.neo4j = neo4j_service
        self.redis = redis_service
        
        # Initialize components
        self.feature_engineer = FeatureEngineer()
        self.ml_model = RiskScoringModel(settings.model_path)
        self.threat_intel = ThreatIntelligenceService()
        self.synthetic_generator = SyntheticDataGenerator()
        
        # Cache settings
        self.cache_ttl = settings.redis_ttl
        self.score_threshold = settings.risk_score_threshold
        
        # Model update tracking
        self.last_model_update = None
        self.model_update_interval = timedelta(hours=1)
    
    async def initialize(self) -> None:
        """Initialize the risk scoring service"""
        self.log_event("Initializing risk scoring service")
        
        try:
            # Initialize ML model
            self.ml_model.initialize_model()
            
            # If model is not trained, train with synthetic data
            if not self.ml_model.is_trained:
                await self._train_initial_model()
            
            # Initialize threat intelligence service
            await self.threat_intel.initialize()
            
            self.log_event("Risk scoring service initialized successfully")
            
        except Exception as e:
            self.log_error(e, {"component": "initialization"})
            raise
    
    async def score_asset(self, request: RiskScoreRequest) -> RiskScoreResponse:
        """Score a single asset"""
        try:
            # Check cache first
            if not request.force_refresh:
                cached_score = await self._get_cached_score(request.asset_id)
                if cached_score:
                    return RiskScoreResponse(
                        success=True,
                        risk_score=cached_score,
                        cached=True
                    )
            
            # Get asset data
            asset = await self._get_asset_data(request.asset_id)
            if not asset:
                return RiskScoreResponse(
                    success=False,
                    error=f"Asset {request.asset_id} not found"
                )
            
            # Calculate risk score
            risk_score = await self._calculate_risk_score(
                asset, 
                include_explanation=request.include_explanation
            )
            
            # Cache the result
            await self._cache_score(risk_score)
            
            # Publish risk score event
            await self._publish_risk_score_event(risk_score)
            
            return RiskScoreResponse(
                success=True,
                risk_score=risk_score,
                cached=False
            )
            
        except Exception as e:
            self.log_error(e, {"asset_id": request.asset_id})
            return RiskScoreResponse(
                success=False,
                error=str(e)
            )
    
    async def score_assets_batch(self, request: BatchRiskScoreRequest) -> BatchRiskScoreResponse:
        """Score multiple assets in batch"""
        try:
            risk_scores = []
            failed_assets = []
            errors = {}
            
            # Process assets in parallel
            tasks = []
            for asset_id in request.asset_ids:
                task = self.score_asset(RiskScoreRequest(
                    asset_id=asset_id,
                    force_refresh=request.force_refresh,
                    include_explanation=request.include_explanation
                ))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                asset_id = request.asset_ids[i]
                
                if isinstance(result, Exception):
                    failed_assets.append(asset_id)
                    errors[asset_id] = str(result)
                elif result.success and result.risk_score:
                    risk_scores.append(result.risk_score)
                else:
                    failed_assets.append(asset_id)
                    errors[asset_id] = result.error or "Unknown error"
            
            return BatchRiskScoreResponse(
                success=True,
                risk_scores=risk_scores,
                failed_assets=failed_assets,
                errors=errors
            )
            
        except Exception as e:
            self.log_error(e, {"batch_size": len(request.asset_ids)})
            return BatchRiskScoreResponse(
                success=False,
                failed_assets=request.asset_ids,
                errors={"batch_error": str(e)}
            )
    
    async def process_event(self, event: Dict[str, Any]) -> None:
        """Process incoming events for risk scoring"""
        try:
            event_type = event.get('type', '')
            
            if event_type == 'asset.discovered.v1':
                await self._handle_asset_discovered(event)
            elif event_type == 'asset.updated.v1':
                await self._handle_asset_updated(event)
            elif event_type in ['push', 'commit', 'release']:
                await self._handle_asset_activity(event)
            else:
                self.log_event("Unhandled event type", event_type=event_type)
                
        except Exception as e:
            self.log_error(e, {"event": event})
    
    async def _calculate_risk_score(self, asset: Asset, include_explanation: bool = True) -> RiskScore:
        """Calculate risk score for an asset"""
        
        # Extract risk factors
        risk_factors = await self._extract_risk_factors(asset)
        
        # Get threat intelligence
        threat_intel = await self._get_threat_intelligence(asset)
        
        # Get AI-specific risks
        ai_risks = await self._get_ai_risks(asset)
        
        # Engineer features
        feature_set = self.feature_engineer.engineer_features(
            asset, risk_factors, threat_intel, ai_risks
        )
        
        # Predict risk score
        risk_score, confidence, anomaly_label, explanation = self.ml_model.predict_single(feature_set)
        
        # Determine risk level
        risk_level = self.ml_model.get_risk_level(risk_score)
        
        # Create component scores
        component_scores = {
            'exposure': risk_factors.exposure * 100,
            'sensitivity': risk_factors.sensitivity * 100,
            'criticality': risk_factors.criticality * 100,
            'vulnerability': risk_factors.vulnerability * 100,
            'threat_intelligence': self._calculate_threat_score(threat_intel),
            'ai_risks': self._calculate_ai_risk_score(ai_risks)
        }
        
        return RiskScore(
            asset_id=asset.id,
            overall_score=risk_score,
            risk_level=risk_level,
            component_scores=component_scores,
            confidence=confidence,
            factors=risk_factors,
            threat_intel=threat_intel,
            ai_risks=ai_risks,
            timestamp=datetime.now(),
            model_version=self.ml_model.model_version,
            explanation=explanation if include_explanation else {}
        )
    
    async def _extract_risk_factors(self, asset: Asset) -> RiskFactors:
        """Extract risk factors from asset data"""
        
        # Calculate exposure based on asset metadata
        exposure = 0.0
        if asset.metadata.get('visibility') == 'public':
            exposure = 0.8
        elif asset.metadata.get('visibility') == 'internal':
            exposure = 0.4
        else:
            exposure = 0.2
        
        # Calculate sensitivity based on asset type and content
        sensitivity = 0.5  # Default
        if asset.type in ['model', 'dataset']:
            sensitivity = 0.8
        elif asset.type == 'document':
            sensitivity = 0.6
        
        # Calculate criticality based on dependencies and usage
        dependency_count = await self._get_dependency_count(asset.id)
        criticality = min(dependency_count / 10.0, 1.0)
        
        # Calculate vulnerability based on age and updates
        age_days = (datetime.now() - asset.created_at).days
        days_since_update = (datetime.now() - asset.updated_at).days
        vulnerability = min((age_days + days_since_update) / 365.0, 1.0)
        
        # Calculate access frequency
        access_frequency = await self._get_access_frequency(asset.id)
        
        # Asset size
        size_mb = float(asset.metadata.get('size_bytes', 0)) / (1024 * 1024)
        
        return RiskFactors(
            exposure=exposure,
            sensitivity=sensitivity,
            criticality=criticality,
            vulnerability=vulnerability,
            access_frequency=access_frequency,
            dependency_count=dependency_count,
            age_days=age_days,
            size_mb=size_mb
        )
    
    async def _get_threat_intelligence(self, asset: Asset) -> Optional[ThreatIntelligence]:
        """Get threat intelligence for an asset"""
        try:
            return await self.threat_intel.get_threat_data(asset)
        except Exception as e:
            self.log_error(e, {"asset_id": asset.id, "component": "threat_intelligence"})
            return None
    
    async def _get_ai_risks(self, asset: Asset) -> Optional[AISpecificRisks]:
        """Calculate AI-specific risks for an asset"""
        if asset.type not in ['model', 'dataset']:
            return None
        
        # Calculate AI-specific risks based on asset metadata
        model_inversion_risk = 0.3 if asset.type == 'model' else 0.0
        membership_inference_risk = 0.4 if asset.type == 'dataset' else 0.2
        data_poisoning_risk = 0.3 if asset.type == 'dataset' else 0.1
        adversarial_attack_risk = 0.5 if asset.type == 'model' else 0.0
        privacy_leakage_risk = 0.4 if 'personal' in asset.description.lower() else 0.2
        
        return AISpecificRisks(
            model_inversion_risk=model_inversion_risk,
            membership_inference_risk=membership_inference_risk,
            data_poisoning_risk=data_poisoning_risk,
            adversarial_attack_risk=adversarial_attack_risk,
            privacy_leakage_risk=privacy_leakage_risk
        )
    
    async def _get_asset_data(self, asset_id: str) -> Optional[Asset]:
        """Get asset data from Neo4j"""
        try:
            asset_data = await self.neo4j.get_asset(asset_id)
            if not asset_data:
                return None
            
            return Asset(**asset_data)
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "neo4j"})
            return None
    
    async def _get_dependency_count(self, asset_id: str) -> int:
        """Get dependency count for an asset"""
        try:
            return await self.neo4j.get_dependency_count(asset_id)
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id})
            return 0
    
    async def _get_access_frequency(self, asset_id: str) -> float:
        """Get access frequency for an asset"""
        try:
            # Get access logs from the last 30 days
            access_count = await self.redis.get_access_count(asset_id, days=30)
            return float(access_count) / 30.0  # Average per day
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id})
            return 0.0
    
    def _calculate_threat_score(self, threat_intel: Optional[ThreatIntelligence]) -> float:
        """Calculate threat intelligence score"""
        if not threat_intel:
            return 0.0
        
        base_score = threat_intel.severity_score * 10  # Scale to 0-100
        
        # Adjust for CVE count
        cve_adjustment = min(threat_intel.cve_count * 5, 30)
        
        # Adjust for exploit availability
        exploit_adjustment = 20 if threat_intel.exploit_available else 0
        
        # Adjust for threat actors
        actor_adjustment = len(threat_intel.threat_actors) * 5
        
        total_score = base_score + cve_adjustment + exploit_adjustment + actor_adjustment
        return min(total_score, 100.0)
    
    def _calculate_ai_risk_score(self, ai_risks: Optional[AISpecificRisks]) -> float:
        """Calculate AI-specific risk score"""
        if not ai_risks:
            return 0.0
        
        risks = [
            ai_risks.model_inversion_risk,
            ai_risks.membership_inference_risk,
            ai_risks.data_poisoning_risk,
            ai_risks.adversarial_attack_risk,
            ai_risks.privacy_leakage_risk
        ]
        
        return np.mean(risks) * 100
    
    async def _get_cached_score(self, asset_id: str) -> Optional[RiskScore]:
        """Get cached risk score"""
        try:
            cached_data = await self.redis.get(f"risk_score:{asset_id}")
            if cached_data:
                return RiskScore(**json.loads(cached_data))
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "cache"})
        
        return None
    
    async def _cache_score(self, risk_score: RiskScore) -> None:
        """Cache risk score"""
        try:
            cache_key = f"risk_score:{risk_score.asset_id}"
            cache_data = risk_score.model_dump_json()
            await self.redis.setex(cache_key, self.cache_ttl, cache_data)
        except Exception as e:
            self.log_error(e, {"asset_id": risk_score.asset_id, "component": "cache"})
    
    async def _publish_risk_score_event(self, risk_score: RiskScore) -> None:
        """Publish risk score event to Kafka"""
        try:
            event = {
                'type': 'risk.score.v1',
                'asset_id': risk_score.asset_id,
                'risk_score': risk_score.overall_score,
                'risk_level': risk_score.risk_level,
                'timestamp': risk_score.timestamp.isoformat(),
                'model_version': risk_score.model_version
            }
            
            # This would be implemented with actual Kafka producer
            self.log_event("Risk score event published", **event)
            
        except Exception as e:
            self.log_error(e, {"asset_id": risk_score.asset_id, "component": "kafka"})
    
    async def _handle_asset_discovered(self, event: Dict[str, Any]) -> None:
        """Handle asset discovered event"""
        asset_id = event.get('asset_id')
        if not asset_id:
            return
        
        # Score the newly discovered asset
        request = RiskScoreRequest(asset_id=asset_id, include_explanation=False)
        await self.score_asset(request)
        
        self.log_event("Asset scored on discovery", asset_id=asset_id)
    
    async def _handle_asset_updated(self, event: Dict[str, Any]) -> None:
        """Handle asset updated event"""
        asset_id = event.get('asset_id')
        if not asset_id:
            return
        
        # Re-score the updated asset
        request = RiskScoreRequest(asset_id=asset_id, force_refresh=True)
        await self.score_asset(request)
        
        self.log_event("Asset re-scored on update", asset_id=asset_id)
    
    async def _handle_asset_activity(self, event: Dict[str, Any]) -> None:
        """Handle asset activity events (push, commit, etc.)"""
        asset_id = event.get('asset_id') or event.get('repository')
        if not asset_id:
            return
        
        # Update access frequency and re-score if needed
        await self.redis.increment_access_count(asset_id)
        
        # Check if re-scoring is needed based on activity
        if await self._should_rescore_on_activity(asset_id, event):
            request = RiskScoreRequest(asset_id=asset_id, force_refresh=True)
            await self.score_asset(request)
    
    async def _should_rescore_on_activity(self, asset_id: str, event: Dict[str, Any]) -> bool:
        """Determine if asset should be re-scored based on activity"""
        # Re-score if it's been more than 1 hour since last score
        last_score_time = await self.redis.get(f"last_score_time:{asset_id}")
        if not last_score_time:
            return True
        
        last_time = datetime.fromisoformat(last_score_time)
        return (datetime.now() - last_time) > timedelta(hours=1)
    
    async def _train_initial_model(self) -> None:
        """Train initial model with synthetic data"""
        self.log_event("Training initial model with synthetic data")
        
        # Generate synthetic training data
        features, targets, feature_names = self.synthetic_generator.generate_training_data(5000)
        
        # Train the model
        training_stats = self.ml_model.train(features, targets, feature_names)
        
        self.log_event("Initial model training completed", **training_stats['val_metrics'])
    
    async def update_model_if_needed(self) -> bool:
        """Update model if needed based on new data"""
        if (self.last_model_update and 
            datetime.now() - self.last_model_update < self.model_update_interval):
            return False
        
        try:
            # This would collect real training data from scored assets
            # For now, we'll use synthetic data
            features, targets, feature_names = self.synthetic_generator.generate_training_data(1000)
            
            # Retrain if needed
            retrained = self.ml_model.retrain_if_needed(features, targets, feature_names)
            
            if retrained:
                self.last_model_update = datetime.now()
                self.log_event("Model updated successfully")
            
            return retrained
            
        except Exception as e:
            self.log_error(e, {"component": "model_update"})
            return False