#!/usr/bin/env python3
"""
Script to test the risk scoring functionality
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.models.asset import Asset, AssetType, AssetSource, RiskScoreRequest
from src.services.risk_scorer import RiskScoringService
from src.services.neo4j_service import Neo4jService
from src.services.redis_service import RedisService
from src.utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def create_test_assets():
    """Create test assets for scoring"""
    return [
        Asset(
            id="test-repo-1",
            type=AssetType.REPOSITORY,
            name="critical-api-service",
            owner="engineering-team",
            source=AssetSource.GITHUB,
            description="Critical API service handling user authentication",
            metadata={
                "visibility": "public",
                "language": "python",
                "size_bytes": 5242880,  # 5MB
                "dependencies": ["flask", "sqlalchemy", "redis", "jwt"],
                "last_commit": "2024-01-15T10:30:00Z"
            },
            created_at=datetime(2023, 6, 1),
            updated_at=datetime(2024, 1, 15),
            last_accessed=datetime(2024, 1, 20),
            tags=["api", "authentication", "critical"],
            status="active"
        ),
        Asset(
            id="test-model-1",
            type=AssetType.MODEL,
            name="user-recommendation-model",
            owner="ml-team",
            source=AssetSource.HUGGINGFACE,
            description="Machine learning model for user recommendations containing personal data",
            metadata={
                "visibility": "private",
                "framework": "tensorflow",
                "size_bytes": 104857600,  # 100MB
                "model_type": "neural_network",
                "accuracy": 0.89
            },
            created_at=datetime(2023, 8, 15),
            updated_at=datetime(2024, 1, 10),
            last_accessed=datetime(2024, 1, 22),
            tags=["ml", "recommendations", "personal"],
            status="active"
        ),
        Asset(
            id="test-dataset-1",
            type=AssetType.DATASET,
            name="customer-transaction-data",
            owner="data-team",
            source=AssetSource.SNOWFLAKE,
            description="Customer transaction dataset with PII and financial information",
            metadata={
                "visibility": "internal",
                "size_bytes": 1073741824,  # 1GB
                "rows": 10000000,
                "columns": 25,
                "contains_pii": True
            },
            created_at=datetime(2023, 3, 1),
            updated_at=datetime(2023, 12, 20),
            last_accessed=datetime(2024, 1, 18),
            tags=["dataset", "transactions", "pii", "financial"],
            status="active"
        )
    ]


class MockNeo4jService:
    """Mock Neo4j service for testing"""
    
    def __init__(self):
        self.assets = {asset.id: asset for asset in create_test_assets()}
    
    async def connect(self):
        pass
    
    async def close(self):
        pass
    
    async def health_check(self):
        pass
    
    async def get_asset(self, asset_id: str):
        asset = self.assets.get(asset_id)
        if asset:
            return asset.model_dump()
        return None
    
    async def get_dependency_count(self, asset_id: str):
        # Mock dependency counts
        counts = {
            "test-repo-1": 15,
            "test-model-1": 3,
            "test-dataset-1": 8
        }
        return counts.get(asset_id, 0)
    
    async def get_dependent_count(self, asset_id: str):
        # Mock dependent counts
        counts = {
            "test-repo-1": 5,
            "test-model-1": 12,
            "test-dataset-1": 20
        }
        return counts.get(asset_id, 0)


class MockRedisService:
    """Mock Redis service for testing"""
    
    def __init__(self):
        self.cache = {}
        self.access_counts = {}
    
    async def connect(self):
        pass
    
    async def close(self):
        pass
    
    async def ping(self):
        return True
    
    async def get(self, key: str):
        return self.cache.get(key)
    
    async def setex(self, key: str, ttl: int, value: str):
        self.cache[key] = value
        return True
    
    async def get_access_count(self, asset_id: str, days: int = 30):
        # Mock access counts
        counts = {
            "test-repo-1": 150,
            "test-model-1": 45,
            "test-dataset-1": 80
        }
        return counts.get(asset_id, 10)
    
    async def increment_access_count(self, asset_id: str):
        current = self.access_counts.get(asset_id, 0)
        self.access_counts[asset_id] = current + 1
        return self.access_counts[asset_id]


async def main():
    """Test risk scoring functionality"""
    logger.info("Starting risk scoring test")
    
    try:
        # Initialize mock services
        neo4j_service = MockNeo4jService()
        redis_service = MockRedisService()
        
        await neo4j_service.connect()
        await redis_service.connect()
        
        # Initialize risk scorer
        risk_scorer = RiskScoringService(neo4j_service, redis_service)
        await risk_scorer.initialize()
        
        logger.info("Services initialized successfully")
        
        # Test scoring individual assets
        test_assets = create_test_assets()
        
        for asset in test_assets:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing asset: {asset.name} ({asset.type})")
            logger.info(f"{'='*60}")
            
            # Create scoring request
            request = RiskScoreRequest(
                asset_id=asset.id,
                force_refresh=True,
                include_explanation=True
            )
            
            # Score the asset
            response = await risk_scorer.score_asset(request)
            
            if response.success and response.risk_score:
                score = response.risk_score
                
                logger.info(f"Risk Score: {score.overall_score:.2f}/100")
                logger.info(f"Risk Level: {score.risk_level}")
                logger.info(f"Confidence: {score.confidence:.3f}")
                logger.info(f"Model Version: {score.model_version}")
                
                logger.info("\nComponent Scores:")
                for component, value in score.component_scores.items():
                    logger.info(f"  {component:<20}: {value:.2f}")
                
                logger.info("\nRisk Factors:")
                factors = score.factors
                logger.info(f"  Exposure:      {factors.exposure:.3f}")
                logger.info(f"  Sensitivity:   {factors.sensitivity:.3f}")
                logger.info(f"  Criticality:   {factors.criticality:.3f}")
                logger.info(f"  Vulnerability: {factors.vulnerability:.3f}")
                logger.info(f"  Access Freq:   {factors.access_frequency:.3f}")
                logger.info(f"  Dependencies:  {factors.dependency_count}")
                logger.info(f"  Age (days):    {factors.age_days}")
                logger.info(f"  Size (MB):     {factors.size_mb:.2f}")
                
                if score.explanation and 'top_factors' in score.explanation:
                    logger.info("\nTop Risk Factors:")
                    for i, (factor_name, factor_data) in enumerate(score.explanation['top_factors'][:5], 1):
                        logger.info(f"  {i}. {factor_name:<25}: {factor_data['contribution']:.4f}")
                
                if score.threat_intel:
                    logger.info(f"\nThreat Intelligence:")
                    logger.info(f"  CVE Count:     {score.threat_intel.cve_count}")
                    logger.info(f"  Severity:      {score.threat_intel.severity_score:.1f}/10")
                    logger.info(f"  Exploit Avail: {score.threat_intel.exploit_available}")
                    logger.info(f"  Threat Actors: {len(score.threat_intel.threat_actors)}")
                
                if score.ai_risks:
                    logger.info(f"\nAI-Specific Risks:")
                    logger.info(f"  Model Inversion:      {score.ai_risks.model_inversion_risk:.3f}")
                    logger.info(f"  Membership Inference: {score.ai_risks.membership_inference_risk:.3f}")
                    logger.info(f"  Data Poisoning:       {score.ai_risks.data_poisoning_risk:.3f}")
                    logger.info(f"  Adversarial Attack:   {score.ai_risks.adversarial_attack_risk:.3f}")
                    logger.info(f"  Privacy Leakage:      {score.ai_risks.privacy_leakage_risk:.3f}")
                
            else:
                logger.error(f"Failed to score asset: {response.error}")
        
        # Test batch scoring
        logger.info(f"\n{'='*60}")
        logger.info("Testing batch scoring")
        logger.info(f"{'='*60}")
        
        from src.models.asset import BatchRiskScoreRequest
        
        batch_request = BatchRiskScoreRequest(
            asset_ids=[asset.id for asset in test_assets],
            force_refresh=True,
            include_explanation=False
        )
        
        batch_response = await risk_scorer.score_assets_batch(batch_request)
        
        if batch_response.success:
            logger.info(f"Batch scoring successful:")
            logger.info(f"  Scored: {len(batch_response.risk_scores)} assets")
            logger.info(f"  Failed: {len(batch_response.failed_assets)} assets")
            
            for score in batch_response.risk_scores:
                logger.info(f"  {score.asset_id}: {score.overall_score:.2f} ({score.risk_level})")
        else:
            logger.error("Batch scoring failed")
        
        logger.info("\nRisk scoring test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in risk scoring test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        if 'neo4j_service' in locals():
            await neo4j_service.close()
        if 'redis_service' in locals():
            await redis_service.close()


if __name__ == "__main__":
    asyncio.run(main())