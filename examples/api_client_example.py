#!/usr/bin/env python3
"""
IARG Risk Scoring API Client Example
Demonstrates how to interact with the risk scoring service via REST API
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, List, Any


class IARGRiskScoringClient:
    """Client for interacting with IARG Risk Scoring Service"""
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        response = await self.client.get(f"{self.base_url}/health")
        return response.json()
    
    async def detailed_health_check(self) -> Dict[str, Any]:
        """Get detailed health check with dependencies"""
        response = await self.client.get(f"{self.base_url}/health/detailed")
        return response.json()
    
    async def score_asset(self, asset_id: str, force_refresh: bool = False, 
                         include_explanation: bool = True) -> Dict[str, Any]:
        """Score a single asset"""
        payload = {
            "asset_id": asset_id,
            "force_refresh": force_refresh,
            "include_explanation": include_explanation
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/score", json=payload)
        return response.json()
    
    async def score_assets_batch(self, asset_ids: List[str], force_refresh: bool = False,
                               include_explanation: bool = True) -> Dict[str, Any]:
        """Score multiple assets in batch"""
        payload = {
            "asset_ids": asset_ids,
            "force_refresh": force_refresh,
            "include_explanation": include_explanation
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/score/batch", json=payload)
        return response.json()
    
    async def get_asset_risk_score(self, asset_id: str, force_refresh: bool = False,
                                 include_explanation: bool = True) -> Dict[str, Any]:
        """Get cached risk score for an asset"""
        params = {
            "force_refresh": force_refresh,
            "include_explanation": include_explanation
        }
        
        response = await self.client.get(f"{self.base_url}/api/v1/score/{asset_id}", params=params)
        return response.json()
    
    async def get_high_risk_assets(self, threshold: float = 70.0, limit: int = 50) -> Dict[str, Any]:
        """Get assets with high risk scores"""
        params = {"threshold": threshold, "limit": limit}
        response = await self.client.get(f"{self.base_url}/api/v1/assets/high-risk", params=params)
        return response.json()
    
    async def get_asset_dependencies(self, asset_id: str) -> Dict[str, Any]:
        """Get asset dependencies and dependents"""
        response = await self.client.get(f"{self.base_url}/api/v1/assets/{asset_id}/dependencies")
        return response.json()
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the risk scoring model"""
        response = await self.client.get(f"{self.base_url}/api/v1/model/info")
        return response.json()
    
    async def get_feature_importance(self) -> Dict[str, Any]:
        """Get feature importance from the model"""
        response = await self.client.get(f"{self.base_url}/api/v1/model/feature-importance")
        return response.json()
    
    async def retrain_model(self) -> Dict[str, Any]:
        """Trigger model retraining"""
        response = await self.client.post(f"{self.base_url}/api/v1/model/retrain")
        return response.json()
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        response = await self.client.get(f"{self.base_url}/api/v1/statistics")
        return response.json()
    
    async def get_risk_level_distribution(self) -> Dict[str, Any]:
        """Get risk level distribution across assets"""
        response = await self.client.get(f"{self.base_url}/api/v1/risk-levels")
        return response.json()
    
    async def handle_asset_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Send asset event for processing"""
        response = await self.client.post(f"{self.base_url}/api/v1/webhook/asset-event", json=event)
        return response.json()


async def demonstrate_api_usage():
    """Demonstrate comprehensive API usage"""
    
    client = IARGRiskScoringClient()
    
    try:
        print("🚀 IARG Risk Scoring API Client Demo")
        print("=" * 50)
        
        # 1. Health Check
        print("\n1️⃣ Health Check")
        health = await client.health_check()
        print(f"   Status: {health.get('status', 'unknown')}")
        
        # 2. Model Information
        print("\n2️⃣ Model Information")
        model_info = await client.get_model_info()
        if model_info.get('success'):
            print(f"   Model Version: {model_info.get('model_version')}")
            print(f"   Is Trained: {model_info.get('is_trained')}")
            print(f"   Features: {model_info.get('feature_count')}")
        
        # 3. Score Individual Assets
        print("\n3️⃣ Individual Asset Scoring")
        test_assets = [
            "critical-auth-api",
            "user-behavior-model", 
            "financial-transactions-dataset"
        ]
        
        for asset_id in test_assets:
            print(f"\n   Scoring: {asset_id}")
            result = await client.score_asset(asset_id, force_refresh=True)
            
            if result.get('success') and result.get('risk_score'):
                score = result['risk_score']
                print(f"   ✅ Score: {score['overall_score']:.1f}/100 ({score['risk_level'].upper()})")
                print(f"   📊 Confidence: {score['confidence']:.1%}")
                
                # Show top risk factors
                if score.get('explanation', {}).get('top_factors'):
                    top_factor = score['explanation']['top_factors'][0]
                    factor_name = top_factor[0].replace('_', ' ').title()
                    print(f"   🔍 Top Risk Factor: {factor_name}")
            else:
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
        
        # 4. Batch Scoring
        print(f"\n4️⃣ Batch Scoring")
        batch_result = await client.score_assets_batch(test_assets, force_refresh=True)
        
        if batch_result.get('success'):
            scores = batch_result.get('risk_scores', [])
            print(f"   ✅ Batch scored {len(scores)} assets")
            
            # Calculate statistics
            if scores:
                risk_scores = [s['overall_score'] for s in scores]
                avg_score = sum(risk_scores) / len(risk_scores)
                max_score = max(risk_scores)
                min_score = min(risk_scores)
                
                print(f"   📊 Average Score: {avg_score:.1f}")
                print(f"   📈 Highest Score: {max_score:.1f}")
                print(f"   📉 Lowest Score: {min_score:.1f}")
        
        # 5. Feature Importance
        print(f"\n5️⃣ Feature Importance Analysis")
        importance = await client.get_feature_importance()
        
        if importance.get('success'):
            features = importance.get('feature_importance', {})
            # Get top 5 most important features
            top_features = sorted(features.items(), key=lambda x: x[1], reverse=True)[:5]
            
            print("   🔍 Top 5 Most Important Features:")
            for i, (feature, score) in enumerate(top_features, 1):
                feature_name = feature.replace('_', ' ').title()
                print(f"   {i}. {feature_name:<25}: {score:.4f}")
        
        # 6. High Risk Assets
        print(f"\n6️⃣ High Risk Assets")
        high_risk = await client.get_high_risk_assets(threshold=60.0, limit=10)
        
        if high_risk.get('success'):
            assets = high_risk.get('assets', [])
            print(f"   🚨 Found {len(assets)} high-risk assets")
            
            for asset in assets[:3]:  # Show top 3
                print(f"   • {asset.get('name', 'Unknown')}: {asset.get('risk_score', 0):.1f}")
        
        # 7. Risk Distribution
        print(f"\n7️⃣ Risk Level Distribution")
        distribution = await client.get_risk_level_distribution()
        
        if distribution.get('success'):
            dist = distribution.get('distribution', {})
            total = distribution.get('total_assets', 0)
            
            print(f"   📊 Total Assets: {total}")
            print(f"   🔴 Critical: {dist.get('high', {}).get('count', 0)} ({dist.get('high', {}).get('percentage', 0):.1f}%)")
            print(f"   🟡 Medium: {dist.get('medium', {}).get('count', 0)} ({dist.get('medium', {}).get('percentage', 0):.1f}%)")
            print(f"   🟢 Low: {dist.get('low', {}).get('count', 0)} ({dist.get('low', {}).get('percentage', 0):.1f}%)")
        
        # 8. Event Processing
        print(f"\n8️⃣ Event Processing")
        test_event = {
            "type": "asset.discovered.v1",
            "asset_id": "new-test-asset",
            "timestamp": datetime.now().isoformat(),
            "source": "github",
            "asset_type": "repository"
        }
        
        event_result = await client.handle_asset_event(test_event)
        if event_result.get('success'):
            print(f"   ✅ Event processed: {event_result.get('event_type')}")
        
        print(f"\n✅ API Demo completed successfully!")
        
    except httpx.ConnectError:
        print("❌ Could not connect to IARG Risk Scoring Service")
        print("   Make sure the service is running on http://localhost:8002")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
    finally:
        await client.close()


async def demonstrate_real_world_scenario():
    """Demonstrate a real-world risk assessment scenario"""
    
    client = IARGRiskScoringClient()
    
    try:
        print("\n" + "=" * 60)
        print("🌍 REAL-WORLD SCENARIO: Security Audit")
        print("=" * 60)
        
        # Scenario: Security team needs to assess risk across all assets
        print("\n📋 Scenario: Quarterly security audit requires risk assessment")
        print("   Goal: Identify high-risk assets requiring immediate attention")
        
        # Step 1: Get high-risk assets
        print("\n🔍 Step 1: Identifying high-risk assets...")
        high_risk_assets = await client.get_high_risk_assets(threshold=70.0, limit=20)
        
        if high_risk_assets.get('success'):
            assets = high_risk_assets.get('assets', [])
            print(f"   Found {len(assets)} assets with risk score ≥ 70")
            
            # Step 2: Detailed analysis of top 3 highest risk assets
            print(f"\n📊 Step 2: Detailed analysis of highest risk assets")
            
            for i, asset in enumerate(assets[:3], 1):
                asset_id = asset.get('id')
                print(f"\n   Asset {i}: {asset.get('name', 'Unknown')}")
                
                # Get detailed risk score
                detailed_score = await client.get_asset_risk_score(
                    asset_id, 
                    force_refresh=True, 
                    include_explanation=True
                )
                
                if detailed_score.get('success') and detailed_score.get('risk_score'):
                    score = detailed_score['risk_score']
                    
                    print(f"   Risk Score: {score['overall_score']:.1f}/100")
                    print(f"   Risk Level: {score['risk_level'].upper()}")
                    
                    # Show component breakdown
                    components = score.get('component_scores', {})
                    print(f"   Component Breakdown:")
                    for comp, value in components.items():
                        if value > 50:  # Only show concerning components
                            print(f"     • {comp.replace('_', ' ').title()}: {value:.1f}")
                    
                    # Get dependencies
                    deps = await client.get_asset_dependencies(asset_id)
                    if deps.get('success'):
                        dep_count = deps.get('dependency_count', 0)
                        dependent_count = deps.get('dependent_count', 0)
                        print(f"   Dependencies: {dep_count} | Dependents: {dependent_count}")
        
        # Step 3: Generate executive summary
        print(f"\n📈 Step 3: Executive Summary")
        
        # Get overall statistics
        stats = await client.get_statistics()
        risk_dist = await client.get_risk_level_distribution()
        
        if stats.get('success') and risk_dist.get('success'):
            total_assets = risk_dist.get('total_assets', 0)
            high_risk_count = risk_dist.get('distribution', {}).get('high', {}).get('count', 0)
            critical_percentage = (high_risk_count / total_assets * 100) if total_assets > 0 else 0
            
            print(f"   📊 Portfolio Risk Assessment:")
            print(f"   • Total Assets Analyzed: {total_assets}")
            print(f"   • High/Critical Risk Assets: {high_risk_count} ({critical_percentage:.1f}%)")
            print(f"   • Immediate Action Required: {min(high_risk_count, 5)} assets")
            
            print(f"\n   💡 Recommendations:")
            if critical_percentage > 20:
                print(f"   🚨 URGENT: {critical_percentage:.1f}% of assets are high-risk")
                print(f"   📋 Recommend immediate security review and remediation plan")
            elif critical_percentage > 10:
                print(f"   ⚠️  ELEVATED: Monitor high-risk assets closely")
                print(f"   📅 Schedule security improvements within 30 days")
            else:
                print(f"   ✅ ACCEPTABLE: Risk levels within normal parameters")
                print(f"   📊 Continue regular monitoring and assessments")
        
        print(f"\n✅ Security audit scenario completed!")
        
    except Exception as e:
        print(f"❌ Scenario failed: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    print("🎯 IARG Risk Scoring API Client Examples")
    print("=" * 50)
    
    # Run basic API demonstration
    asyncio.run(demonstrate_api_usage())
    
    # Run real-world scenario
    asyncio.run(demonstrate_real_world_scenario())