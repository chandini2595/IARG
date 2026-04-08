#!/usr/bin/env python3
"""
Comprehensive Risk Scoring Demo
Demonstrates how to score any asset with full risk assessment capabilities
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add the score service to path
sys.path.insert(0, str(Path(__file__).parent.parent / "app/score/src"))

from models.asset import Asset, AssetType, AssetSource, RiskScoreRequest
from services.risk_scorer import RiskScoringService
from services.neo4j_service import Neo4jService
from services.redis_service import RedisService
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


class ComprehensiveRiskScoringDemo:
    """Comprehensive demonstration of risk scoring capabilities"""
    
    def __init__(self):
        self.neo4j_service = None
        self.redis_service = None
        self.risk_scorer = None
    
    async def initialize_services(self):
        """Initialize mock services for demonstration"""
        # Use mock services for demo
        self.neo4j_service = MockNeo4jService()
        self.redis_service = MockRedisService()
        
        await self.neo4j_service.connect()
        await self.redis_service.connect()
        
        # Initialize risk scorer
        self.risk_scorer = RiskScoringService(self.neo4j_service, self.redis_service)
        await self.risk_scorer.initialize()
        
        logger.info("Services initialized successfully")
    
    async def demonstrate_comprehensive_scoring(self):
        """Demonstrate comprehensive risk scoring for various asset types"""
        
        # Create diverse test assets
        test_assets = self.create_diverse_test_assets()
        
        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE RISK SCORING DEMONSTRATION")
        print("="*80)
        
        for i, asset in enumerate(test_assets, 1):
            await self.score_and_analyze_asset(asset, i, len(test_assets))
        
        # Demonstrate batch scoring
        await self.demonstrate_batch_scoring(test_assets)
        
        # Demonstrate real-time event processing
        await self.demonstrate_event_processing()
        
        print("\n" + "="*80)
        print("✅ COMPREHENSIVE RISK SCORING DEMO COMPLETED")
        print("="*80)
    
    def create_diverse_test_assets(self) -> List[Asset]:
        """Create diverse assets representing different risk profiles"""
        return [
            # High-risk public API with vulnerabilities
            Asset(
                id="critical-auth-api",
                type=AssetType.REPOSITORY,
                name="authentication-service",
                owner="security-team",
                source=AssetSource.GITHUB,
                description="Critical authentication API with OAuth implementation and user data access",
                metadata={
                    "visibility": "public",
                    "language": "javascript",
                    "size_bytes": 15728640,  # 15MB
                    "dependencies": ["express", "jsonwebtoken", "bcrypt", "lodash", "moment"],
                    "last_commit": "2024-01-10T14:30:00Z",
                    "open_issues": 23,
                    "contributors": 8,
                    "stars": 1250,
                    "forks": 89
                },
                created_at=datetime(2022, 3, 15),
                updated_at=datetime(2024, 1, 10),
                last_accessed=datetime(2024, 1, 25),
                tags=["api", "authentication", "oauth", "critical", "public"],
                status="active"
            ),
            
            # AI model with privacy concerns
            Asset(
                id="user-behavior-model",
                type=AssetType.MODEL,
                name="user-behavior-prediction-model",
                owner="ml-research-team",
                source=AssetSource.HUGGINGFACE,
                description="Deep learning model trained on user behavioral data for personalization, contains potential PII patterns",
                metadata={
                    "visibility": "private",
                    "framework": "pytorch",
                    "model_type": "transformer",
                    "size_bytes": 524288000,  # 500MB
                    "accuracy": 0.94,
                    "training_data_size": "10M samples",
                    "contains_personal_data": True,
                    "model_version": "v2.1.3",
                    "inference_endpoint": "https://api.company.com/predict"
                },
                created_at=datetime(2023, 8, 20),
                updated_at=datetime(2024, 1, 18),
                last_accessed=datetime(2024, 1, 24),
                tags=["ml", "transformer", "behavioral", "personalization", "pii"],
                status="active"
            ),
            
            # Sensitive financial dataset
            Asset(
                id="financial-transactions-dataset",
                type=AssetType.DATASET,
                name="customer-financial-transactions",
                owner="data-analytics-team",
                source=AssetSource.SNOWFLAKE,
                description="Comprehensive financial transaction dataset containing customer payment histories, account balances, and transaction patterns",
                metadata={
                    "visibility": "internal",
                    "size_bytes": 5368709120,  # 5GB
                    "rows": 50000000,
                    "columns": 45,
                    "contains_pii": True,
                    "contains_financial_data": True,
                    "data_classification": "highly_confidential",
                    "retention_period": "7_years",
                    "encryption_status": "encrypted_at_rest",
                    "access_controls": "rbac_enabled"
                },
                created_at=datetime(2021, 11, 5),
                updated_at=datetime(2024, 1, 20),
                last_accessed=datetime(2024, 1, 23),
                tags=["dataset", "financial", "transactions", "pii", "confidential"],
                status="active"
            ),
            
            # Legacy code repository
            Asset(
                id="legacy-payment-processor",
                type=AssetType.CODE,
                name="legacy-payment-processing-system",
                owner="payments-team",
                source=AssetSource.GITHUB,
                description="Legacy payment processing system written in older frameworks, handles credit card transactions",
                metadata={
                    "visibility": "private",
                    "language": "java",
                    "framework": "spring-2.5",
                    "size_bytes": 31457280,  # 30MB
                    "last_security_scan": "2023-06-15T10:00:00Z",
                    "known_vulnerabilities": 12,
                    "dependencies_outdated": True,
                    "compliance_status": "pci_dss_required",
                    "business_criticality": "high"
                },
                created_at=datetime(2019, 2, 10),
                updated_at=datetime(2023, 11, 30),
                last_accessed=datetime(2024, 1, 22),
                tags=["legacy", "payments", "java", "spring", "pci", "critical"],
                status="active"
            ),
            
            # Public research dataset
            Asset(
                id="public-research-dataset",
                type=AssetType.DATASET,
                name="climate-research-data",
                owner="research-team",
                source=AssetSource.GITHUB,
                description="Open climate research dataset for academic use, anonymized and publicly available",
                metadata={
                    "visibility": "public",
                    "size_bytes": 104857600,  # 100MB
                    "rows": 1000000,
                    "columns": 15,
                    "license": "cc_by_4.0",
                    "data_classification": "public",
                    "anonymized": True,
                    "research_purpose": True
                },
                created_at=datetime(2023, 5, 12),
                updated_at=datetime(2024, 1, 15),
                last_accessed=datetime(2024, 1, 25),
                tags=["research", "climate", "public", "anonymized", "academic"],
                status="active"
            )
        ]
    
    async def score_and_analyze_asset(self, asset: Asset, index: int, total: int):
        """Score and provide comprehensive analysis for an asset"""
        
        print(f"\n📊 ASSET {index}/{total}: {asset.name.upper()}")
        print("-" * 60)
        print(f"Type: {asset.type.value.title()}")
        print(f"Source: {asset.source.value.title()}")
        print(f"Owner: {asset.owner}")
        print(f"Description: {asset.description[:100]}...")
        
        # Create scoring request
        request = RiskScoreRequest(
            asset_id=asset.id,
            force_refresh=True,
            include_explanation=True
        )
        
        # Score the asset
        response = await self.risk_scorer.score_asset(request)
        
        if not response.success or not response.risk_score:
            print(f"❌ Failed to score asset: {response.error}")
            return
        
        score = response.risk_score
        
        # Display comprehensive risk analysis
        self.display_risk_overview(score)
        self.display_component_analysis(score)
        self.display_risk_factors(score)
        self.display_threat_intelligence(score)
        self.display_ai_specific_risks(score)
        self.display_top_risk_factors(score)
        self.display_recommendations(score, asset)
    
    def display_risk_overview(self, score):
        """Display risk overview with visual indicators"""
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "critical": "🔴"
        }
        
        print(f"\n🎯 RISK OVERVIEW")
        print(f"   Overall Score: {score.overall_score:.1f}/100 {risk_emoji.get(score.risk_level.value, '⚪')}")
        print(f"   Risk Level: {score.risk_level.value.upper()}")
        print(f"   Confidence: {score.confidence:.1%}")
        print(f"   Model Version: {score.model_version}")
        print(f"   Timestamp: {score.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def display_component_analysis(self, score):
        """Display component score breakdown"""
        print(f"\n📈 COMPONENT SCORES")
        components = score.component_scores
        
        for component, value in components.items():
            bar_length = int(value / 5)  # Scale to 20 chars max
            bar = "█" * bar_length + "░" * (20 - bar_length)
            print(f"   {component.replace('_', ' ').title():<20}: {value:5.1f} [{bar}]")
    
    def display_risk_factors(self, score):
        """Display detailed risk factors"""
        print(f"\n⚠️  RISK FACTORS")
        factors = score.factors
        
        print(f"   Exposure Level:     {factors.exposure:.3f} ({'High' if factors.exposure > 0.7 else 'Medium' if factors.exposure > 0.3 else 'Low'})")
        print(f"   Sensitivity:        {factors.sensitivity:.3f} ({'High' if factors.sensitivity > 0.7 else 'Medium' if factors.sensitivity > 0.3 else 'Low'})")
        print(f"   Business Critical:  {factors.criticality:.3f} ({'High' if factors.criticality > 0.7 else 'Medium' if factors.criticality > 0.3 else 'Low'})")
        print(f"   Vulnerability:      {factors.vulnerability:.3f} ({'High' if factors.vulnerability > 0.7 else 'Medium' if factors.vulnerability > 0.3 else 'Low'})")
        print(f"   Access Frequency:   {factors.access_frequency:.1f} accesses/day")
        print(f"   Dependencies:       {factors.dependency_count} dependencies")
        print(f"   Age:                {factors.age_days} days")
        print(f"   Size:               {factors.size_mb:.1f} MB")
    
    def display_threat_intelligence(self, score):
        """Display threat intelligence information"""
        if not score.threat_intel:
            print(f"\n🛡️  THREAT INTELLIGENCE: No threat data available")
            return
        
        threat = score.threat_intel
        print(f"\n🛡️  THREAT INTELLIGENCE")
        print(f"   CVE Count:          {threat.cve_count} known vulnerabilities")
        print(f"   Severity Score:     {threat.severity_score:.1f}/10.0")
        print(f"   Exploit Available:  {'Yes ⚠️' if threat.exploit_available else 'No ✅'}")
        print(f"   Threat Actors:      {len(threat.threat_actors)} identified")
        
        if threat.threat_actors:
            print(f"   Actor Types:        {', '.join(threat.threat_actors[:3])}")
        
        print(f"   Last Updated:       {threat.last_updated.strftime('%Y-%m-%d %H:%M')}")
    
    def display_ai_specific_risks(self, score):
        """Display AI-specific risk factors"""
        if not score.ai_risks:
            print(f"\n🤖 AI-SPECIFIC RISKS: Not applicable for this asset type")
            return
        
        ai_risks = score.ai_risks
        print(f"\n🤖 AI-SPECIFIC RISKS")
        print(f"   Model Inversion:       {ai_risks.model_inversion_risk:.3f} ({'High' if ai_risks.model_inversion_risk > 0.7 else 'Medium' if ai_risks.model_inversion_risk > 0.3 else 'Low'})")
        print(f"   Membership Inference:  {ai_risks.membership_inference_risk:.3f} ({'High' if ai_risks.membership_inference_risk > 0.7 else 'Medium' if ai_risks.membership_inference_risk > 0.3 else 'Low'})")
        print(f"   Data Poisoning:        {ai_risks.data_poisoning_risk:.3f} ({'High' if ai_risks.data_poisoning_risk > 0.7 else 'Medium' if ai_risks.data_poisoning_risk > 0.3 else 'Low'})")
        print(f"   Adversarial Attacks:   {ai_risks.adversarial_attack_risk:.3f} ({'High' if ai_risks.adversarial_attack_risk > 0.7 else 'Medium' if ai_risks.adversarial_attack_risk > 0.3 else 'Low'})")
        print(f"   Privacy Leakage:       {ai_risks.privacy_leakage_risk:.3f} ({'High' if ai_risks.privacy_leakage_risk > 0.7 else 'Medium' if ai_risks.privacy_leakage_risk > 0.3 else 'Low'})")
    
    def display_top_risk_factors(self, score):
        """Display top contributing risk factors"""
        if not score.explanation or 'top_factors' not in score.explanation:
            return
        
        print(f"\n🔍 TOP RISK CONTRIBUTORS")
        top_factors = score.explanation['top_factors'][:5]
        
        for i, (factor_name, factor_data) in enumerate(top_factors, 1):
            contribution = factor_data['contribution']
            value = factor_data['value']
            importance = factor_data['importance']
            
            print(f"   {i}. {factor_name.replace('_', ' ').title():<25}")
            print(f"      Value: {value:.3f} | Importance: {importance:.3f} | Contribution: {contribution:.4f}")
    
    def display_recommendations(self, score, asset):
        """Display security recommendations based on risk assessment"""
        print(f"\n💡 SECURITY RECOMMENDATIONS")
        
        recommendations = []
        
        # Risk level based recommendations
        if score.overall_score >= 80:
            recommendations.append("🚨 CRITICAL: Immediate security review required")
            recommendations.append("🔒 Implement additional access controls")
            recommendations.append("📊 Enable continuous monitoring")
        elif score.overall_score >= 60:
            recommendations.append("⚠️  HIGH RISK: Schedule security assessment within 7 days")
            recommendations.append("🔐 Review and update access permissions")
        elif score.overall_score >= 30:
            recommendations.append("⚡ MEDIUM RISK: Include in next security review cycle")
        else:
            recommendations.append("✅ LOW RISK: Maintain current security posture")
        
        # Component-specific recommendations
        components = score.component_scores
        
        if components.get('exposure', 0) > 70:
            recommendations.append("🌐 Reduce public exposure or add authentication")
        
        if components.get('vulnerability', 0) > 70:
            recommendations.append("🔧 Update dependencies and patch vulnerabilities")
        
        if components.get('threat_intelligence', 0) > 50:
            recommendations.append("🛡️  Apply security patches for known CVEs")
        
        if components.get('ai_risks', 0) > 50:
            recommendations.append("🤖 Implement AI-specific security controls")
        
        # Asset-specific recommendations
        if asset.type == AssetType.DATASET and score.factors.sensitivity > 0.7:
            recommendations.append("🔐 Enable data encryption and access logging")
        
        if asset.type == AssetType.MODEL and score.ai_risks:
            if score.ai_risks.privacy_leakage_risk > 0.5:
                recommendations.append("🔒 Implement differential privacy techniques")
        
        if score.factors.age_days > 365:
            recommendations.append("📅 Schedule regular security updates")
        
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    
    async def demonstrate_batch_scoring(self, assets: List[Asset]):
        """Demonstrate batch scoring capabilities"""
        print(f"\n" + "="*60)
        print("🚀 BATCH SCORING DEMONSTRATION")
        print("="*60)
        
        from models.asset import BatchRiskScoreRequest
        
        # Create batch request
        batch_request = BatchRiskScoreRequest(
            asset_ids=[asset.id for asset in assets],
            force_refresh=True,
            include_explanation=False
        )
        
        print(f"Scoring {len(assets)} assets in batch...")
        
        # Execute batch scoring
        batch_response = await self.risk_scorer.score_assets_batch(batch_request)
        
        if batch_response.success:
            print(f"✅ Batch scoring completed successfully")
            print(f"   Successful: {len(batch_response.risk_scores)} assets")
            print(f"   Failed: {len(batch_response.failed_assets)} assets")
            
            # Display batch results summary
            print(f"\n📊 BATCH RESULTS SUMMARY")
            risk_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            total_score = 0
            
            for score in batch_response.risk_scores:
                risk_distribution[score.risk_level.value] += 1
                total_score += score.overall_score
                print(f"   {score.asset_id:<30}: {score.overall_score:5.1f} ({score.risk_level.value.upper()})")
            
            avg_score = total_score / len(batch_response.risk_scores) if batch_response.risk_scores else 0
            
            print(f"\n📈 RISK DISTRIBUTION")
            print(f"   Average Score: {avg_score:.1f}")
            print(f"   Low Risk:      {risk_distribution['low']} assets")
            print(f"   Medium Risk:   {risk_distribution['medium']} assets") 
            print(f"   High Risk:     {risk_distribution['high']} assets")
            print(f"   Critical Risk: {risk_distribution['critical']} assets")
        else:
            print(f"❌ Batch scoring failed")
    
    async def demonstrate_event_processing(self):
        """Demonstrate real-time event processing"""
        print(f"\n" + "="*60)
        print("⚡ REAL-TIME EVENT PROCESSING DEMONSTRATION")
        print("="*60)
        
        # Simulate various events
        events = [
            {
                "type": "asset.discovered.v1",
                "asset_id": "new-api-service",
                "timestamp": datetime.now().isoformat(),
                "source": "github",
                "asset_type": "repository"
            },
            {
                "type": "asset.updated.v1", 
                "asset_id": "critical-auth-api",
                "timestamp": datetime.now().isoformat(),
                "changes": ["dependencies", "security_config"]
            },
            {
                "type": "push",
                "repository": "legacy-payment-processor",
                "commits": 3,
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        for event in events:
            print(f"\n🔄 Processing event: {event['type']}")
            print(f"   Asset: {event.get('asset_id', event.get('repository', 'unknown'))}")
            
            # Process event
            await self.risk_scorer.process_event(event)
            print(f"   ✅ Event processed successfully")
    
    async def cleanup(self):
        """Cleanup services"""
        if self.neo4j_service:
            await self.neo4j_service.close()
        if self.redis_service:
            await self.redis_service.close()


# Mock services for demonstration
class MockNeo4jService:
    def __init__(self):
        self.assets = {}
    
    async def connect(self): pass
    async def close(self): pass
    async def health_check(self): pass
    
    async def get_asset(self, asset_id: str):
        # Return mock asset data
        return {
            "id": asset_id,
            "type": "repository",
            "name": asset_id.replace("-", " ").title(),
            "owner": "demo-team",
            "source": "github",
            "created_at": datetime.now() - timedelta(days=100),
            "updated_at": datetime.now() - timedelta(days=1),
            "metadata": {"visibility": "private", "size_bytes": 1048576}
        }
    
    async def get_dependency_count(self, asset_id: str):
        return hash(asset_id) % 20  # Mock dependency count
    
    async def get_dependent_count(self, asset_id: str):
        return hash(asset_id) % 15  # Mock dependent count


class MockRedisService:
    def __init__(self):
        self.cache = {}
    
    async def connect(self): pass
    async def close(self): pass
    async def ping(self): return True
    
    async def get(self, key: str): return self.cache.get(key)
    async def setex(self, key: str, ttl: int, value: str): 
        self.cache[key] = value
        return True
    
    async def get_access_count(self, asset_id: str, days: int = 30):
        return hash(asset_id) % 100  # Mock access count
    
    async def increment_access_count(self, asset_id: str):
        return hash(asset_id) % 50


async def main():
    """Run the comprehensive risk scoring demonstration"""
    demo = ComprehensiveRiskScoringDemo()
    
    try:
        await demo.initialize_services()
        await demo.demonstrate_comprehensive_scoring()
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())