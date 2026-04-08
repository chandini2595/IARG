"""
Feature engineering for risk scoring models
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from src.models.asset import Asset, RiskFactors, ThreatIntelligence, AISpecificRisks
from src.utils.logging import LoggerMixin


@dataclass
class FeatureSet:
    """Container for engineered features"""
    features: np.ndarray
    feature_names: List[str]
    metadata: Dict[str, Any]


class FeatureEngineer(LoggerMixin):
    """Feature engineering for risk scoring"""
    
    def __init__(self):
        self.feature_names = [
            # Basic asset features
            'asset_age_days',
            'asset_size_log',
            'access_frequency_normalized',
            'dependency_count_log',
            
            # Risk factors
            'exposure_score',
            'sensitivity_score',
            'criticality_score',
            'vulnerability_score',
            
            # Asset type encoding
            'is_repository',
            'is_model',
            'is_dataset',
            'is_document',
            'is_code',
            'is_api',
            
            # Source encoding
            'is_github',
            'is_huggingface',
            'is_snowflake',
            'is_google_drive',
            
            # Temporal features
            'days_since_last_access',
            'is_recently_accessed',
            'is_stale_asset',
            
            # Security features
            'has_public_exposure',
            'has_sensitive_data',
            'is_business_critical',
            
            # Threat intelligence features
            'cve_count_log',
            'severity_score_normalized',
            'has_exploit_available',
            'threat_actor_count',
            
            # AI-specific features
            'model_inversion_risk',
            'membership_inference_risk',
            'data_poisoning_risk',
            'adversarial_attack_risk',
            'privacy_leakage_risk',
            
            # Derived features
            'risk_velocity',
            'exposure_criticality_interaction',
            'age_access_ratio',
            'vulnerability_exposure_product',
            'composite_ai_risk'
        ]
    
    def engineer_features(
        self,
        asset: Asset,
        risk_factors: RiskFactors,
        threat_intel: Optional[ThreatIntelligence] = None,
        ai_risks: Optional[AISpecificRisks] = None
    ) -> FeatureSet:
        """Engineer features for a single asset"""
        
        features = []
        
        # Basic asset features
        features.extend(self._extract_basic_features(asset, risk_factors))
        
        # Asset type encoding (one-hot)
        features.extend(self._encode_asset_type(asset.type))
        
        # Source encoding (one-hot)
        features.extend(self._encode_asset_source(asset.source))
        
        # Temporal features
        features.extend(self._extract_temporal_features(asset, risk_factors))
        
        # Security features
        features.extend(self._extract_security_features(risk_factors))
        
        # Threat intelligence features
        features.extend(self._extract_threat_features(threat_intel))
        
        # AI-specific features
        features.extend(self._extract_ai_features(ai_risks))
        
        # Derived features
        features.extend(self._extract_derived_features(
            asset, risk_factors, threat_intel, ai_risks
        ))
        
        feature_array = np.array(features, dtype=np.float32)
        
        # Handle any NaN values
        feature_array = np.nan_to_num(feature_array, nan=0.0, posinf=1.0, neginf=0.0)
        
        return FeatureSet(
            features=feature_array,
            feature_names=self.feature_names.copy(),
            metadata={
                'asset_id': asset.id,
                'asset_type': asset.type,
                'timestamp': datetime.now(),
                'feature_count': len(features)
            }
        )
    
    def engineer_batch_features(
        self,
        assets: List[Asset],
        risk_factors_list: List[RiskFactors],
        threat_intel_list: Optional[List[ThreatIntelligence]] = None,
        ai_risks_list: Optional[List[AISpecificRisks]] = None
    ) -> Tuple[np.ndarray, List[str], List[Dict[str, Any]]]:
        """Engineer features for multiple assets"""
        
        if not assets:
            return np.array([]), [], []
        
        # Ensure lists are same length
        n_assets = len(assets)
        if len(risk_factors_list) != n_assets:
            raise ValueError("risk_factors_list must have same length as assets")
        
        if threat_intel_list is None:
            threat_intel_list = [None] * n_assets
        if ai_risks_list is None:
            ai_risks_list = [None] * n_assets
        
        feature_sets = []
        metadata_list = []
        
        for i, asset in enumerate(assets):
            try:
                feature_set = self.engineer_features(
                    asset,
                    risk_factors_list[i],
                    threat_intel_list[i],
                    ai_risks_list[i]
                )
                feature_sets.append(feature_set.features)
                metadata_list.append(feature_set.metadata)
            except Exception as e:
                self.log_error(e, {'asset_id': asset.id})
                # Use zero features for failed assets
                feature_sets.append(np.zeros(len(self.feature_names), dtype=np.float32))
                metadata_list.append({
                    'asset_id': asset.id,
                    'error': str(e),
                    'timestamp': datetime.now()
                })
        
        features_matrix = np.vstack(feature_sets)
        
        return features_matrix, self.feature_names.copy(), metadata_list
    
    def _extract_basic_features(self, asset: Asset, risk_factors: RiskFactors) -> List[float]:
        """Extract basic asset features"""
        now = datetime.now()
        age_days = (now - asset.created_at).days
        
        return [
            float(age_days),  # asset_age_days
            np.log1p(risk_factors.size_mb),  # asset_size_log
            self._normalize_frequency(risk_factors.access_frequency),  # access_frequency_normalized
            np.log1p(risk_factors.dependency_count),  # dependency_count_log
        ]
    
    def _encode_asset_type(self, asset_type: str) -> List[float]:
        """One-hot encode asset type"""
        types = ['repository', 'model', 'dataset', 'document', 'code', 'api']
        return [1.0 if asset_type == t else 0.0 for t in types]
    
    def _encode_asset_source(self, source: str) -> List[float]:
        """One-hot encode asset source"""
        sources = ['github', 'huggingface', 'snowflake', 'google_drive']
        return [1.0 if source == s else 0.0 for s in sources]
    
    def _extract_temporal_features(self, asset: Asset, risk_factors: RiskFactors) -> List[float]:
        """Extract temporal features"""
        now = datetime.now()
        
        if asset.last_accessed:
            days_since_access = (now - asset.last_accessed).days
            is_recently_accessed = 1.0 if days_since_access <= 7 else 0.0
        else:
            days_since_access = (now - asset.created_at).days
            is_recently_accessed = 0.0
        
        is_stale = 1.0 if days_since_access > 90 else 0.0
        
        return [
            float(days_since_access),  # days_since_last_access
            is_recently_accessed,      # is_recently_accessed
            is_stale                   # is_stale_asset
        ]
    
    def _extract_security_features(self, risk_factors: RiskFactors) -> List[float]:
        """Extract security-related features"""
        return [
            1.0 if risk_factors.exposure > 0.7 else 0.0,      # has_public_exposure
            1.0 if risk_factors.sensitivity > 0.7 else 0.0,   # has_sensitive_data
            1.0 if risk_factors.criticality > 0.7 else 0.0    # is_business_critical
        ]
    
    def _extract_threat_features(self, threat_intel: Optional[ThreatIntelligence]) -> List[float]:
        """Extract threat intelligence features"""
        if not threat_intel:
            return [0.0, 0.0, 0.0, 0.0]
        
        return [
            np.log1p(threat_intel.cve_count),                    # cve_count_log
            threat_intel.severity_score / 10.0,                 # severity_score_normalized
            1.0 if threat_intel.exploit_available else 0.0,     # has_exploit_available
            float(len(threat_intel.threat_actors))              # threat_actor_count
        ]
    
    def _extract_ai_features(self, ai_risks: Optional[AISpecificRisks]) -> List[float]:
        """Extract AI-specific risk features"""
        if not ai_risks:
            return [0.0, 0.0, 0.0, 0.0, 0.0]
        
        return [
            ai_risks.model_inversion_risk,      # model_inversion_risk
            ai_risks.membership_inference_risk, # membership_inference_risk
            ai_risks.data_poisoning_risk,       # data_poisoning_risk
            ai_risks.adversarial_attack_risk,   # adversarial_attack_risk
            ai_risks.privacy_leakage_risk       # privacy_leakage_risk
        ]
    
    def _extract_derived_features(
        self,
        asset: Asset,
        risk_factors: RiskFactors,
        threat_intel: Optional[ThreatIntelligence],
        ai_risks: Optional[AISpecificRisks]
    ) -> List[float]:
        """Extract derived/interaction features"""
        
        # Risk velocity (change in risk over time)
        now = datetime.now()
        age_days = max((now - asset.created_at).days, 1)
        risk_velocity = risk_factors.vulnerability / age_days
        
        # Interaction features
        exposure_criticality = risk_factors.exposure * risk_factors.criticality
        
        # Age-access ratio
        if asset.last_accessed:
            days_since_access = (now - asset.last_accessed).days
            age_access_ratio = age_days / max(days_since_access, 1)
        else:
            age_access_ratio = age_days
        
        # Vulnerability-exposure product
        vuln_exposure_product = risk_factors.vulnerability * risk_factors.exposure
        
        # Composite AI risk
        if ai_risks:
            composite_ai_risk = np.mean([
                ai_risks.model_inversion_risk,
                ai_risks.membership_inference_risk,
                ai_risks.data_poisoning_risk,
                ai_risks.adversarial_attack_risk,
                ai_risks.privacy_leakage_risk
            ])
        else:
            composite_ai_risk = 0.0
        
        return [
            risk_velocity,              # risk_velocity
            exposure_criticality,       # exposure_criticality_interaction
            age_access_ratio,          # age_access_ratio
            vuln_exposure_product,     # vulnerability_exposure_product
            composite_ai_risk          # composite_ai_risk
        ]
    
    def _normalize_frequency(self, frequency: float) -> float:
        """Normalize access frequency using log transformation"""
        return np.log1p(frequency) / np.log1p(1000)  # Assume max frequency of 1000
    
    def get_feature_importance_names(self) -> List[str]:
        """Get feature names for importance analysis"""
        return self.feature_names.copy()
    
    def create_feature_dataframe(self, feature_set: FeatureSet) -> pd.DataFrame:
        """Create pandas DataFrame from feature set"""
        return pd.DataFrame(
            feature_set.features.reshape(1, -1),
            columns=feature_set.feature_names
        )