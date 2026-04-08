"""
Machine Learning models for risk scoring
"""

import numpy as np
import pandas as pd
import joblib
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import os
from pathlib import Path

from src.models.asset import RiskLevel
from src.services.feature_engineering import FeatureSet
from src.utils.logging import LoggerMixin


class RiskScoringModel(LoggerMixin):
    """XGBoost-based risk scoring model"""
    
    def __init__(self, model_path: str = "models/"):
        self.model_path = Path(model_path)
        self.model_path.mkdir(exist_ok=True)
        
        # Model components
        self.xgb_model: Optional[xgb.XGBRegressor] = None
        self.anomaly_detector: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        
        # Model metadata
        self.model_version = "1.0.0"
        self.feature_names: List[str] = []
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}
        
        # Model parameters
        self.xgb_params = {
            'n_estimators': 200,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1,
            'objective': 'reg:squarederror',
            'eval_metric': 'rmse'
        }
        
        self.anomaly_params = {
            'contamination': 0.1,
            'random_state': 42,
            'n_jobs': -1
        }
    
    def initialize_model(self) -> None:
        """Initialize the model components"""
        try:
            # Try to load existing model
            self.load_model()
            self.log_event("Model loaded successfully", version=self.model_version)
        except Exception as e:
            # Initialize new model
            self.log_event("Initializing new model", error=str(e))
            self._create_new_model()
    
    def _create_new_model(self) -> None:
        """Create new model instances"""
        self.xgb_model = xgb.XGBRegressor(**self.xgb_params)
        self.anomaly_detector = IsolationForest(**self.anomaly_params)
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def train(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        feature_names: List[str],
        validation_split: float = 0.2
    ) -> Dict[str, Any]:
        """Train the risk scoring model"""
        
        if features.shape[0] == 0:
            raise ValueError("No training data provided")
        
        self.log_event("Starting model training", 
                      samples=features.shape[0], 
                      features=features.shape[1])
        
        # Store feature names
        self.feature_names = feature_names.copy()
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            features, targets, test_size=validation_split, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # Train XGBoost model
        self.xgb_model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_val_scaled, y_val)],
            early_stopping_rounds=20,
            verbose=False
        )
        
        # Train anomaly detector
        self.anomaly_detector.fit(X_train_scaled)
        
        # Evaluate model
        train_pred = self.xgb_model.predict(X_train_scaled)
        val_pred = self.xgb_model.predict(X_val_scaled)
        
        # Calculate metrics
        train_metrics = self._calculate_metrics(y_train, train_pred)
        val_metrics = self._calculate_metrics(y_val, val_pred)
        
        # Cross-validation
        cv_scores = cross_val_score(
            self.xgb_model, X_train_scaled, y_train, 
            cv=5, scoring='neg_mean_squared_error'
        )
        
        # Store training statistics
        self.training_stats = {
            'timestamp': datetime.now(),
            'samples': features.shape[0],
            'features': features.shape[1],
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'cv_rmse_mean': np.sqrt(-cv_scores.mean()),
            'cv_rmse_std': np.sqrt(cv_scores.std()),
            'feature_importance': self._get_feature_importance()
        }
        
        self.is_trained = True
        
        # Save model
        self.save_model()
        
        self.log_event("Model training completed", 
                      train_rmse=train_metrics['rmse'],
                      val_rmse=val_metrics['rmse'])
        
        return self.training_stats
    
    def predict(self, features: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict risk scores
        
        Returns:
            risk_scores: Predicted risk scores (0-100)
            confidence: Prediction confidence (0-1)
            anomaly_scores: Anomaly scores (-1 for anomalies, 1 for normal)
        """
        if not self.is_trained:
            raise ValueError("Model is not trained")
        
        if features.shape[1] != len(self.feature_names):
            raise ValueError(f"Expected {len(self.feature_names)} features, got {features.shape[1]}")
        
        # Scale features
        features_scaled = self.scaler.transform(features)
        
        # Predict risk scores
        raw_scores = self.xgb_model.predict(features_scaled)
        
        # Clip and scale to 0-100 range
        risk_scores = np.clip(raw_scores * 100, 0, 100)
        
        # Calculate confidence based on prediction variance
        confidence = self._calculate_confidence(features_scaled, raw_scores)
        
        # Detect anomalies
        anomaly_scores = self.anomaly_detector.decision_function(features_scaled)
        anomaly_labels = self.anomaly_detector.predict(features_scaled)
        
        return risk_scores, confidence, anomaly_labels
    
    def predict_single(self, feature_set: FeatureSet) -> Tuple[float, float, int, Dict[str, Any]]:
        """
        Predict risk score for a single asset
        
        Returns:
            risk_score: Risk score (0-100)
            confidence: Prediction confidence (0-1)
            anomaly_label: Anomaly label (-1 for anomaly, 1 for normal)
            explanation: Feature importance explanation
        """
        features = feature_set.features.reshape(1, -1)
        risk_scores, confidence, anomaly_labels = self.predict(features)
        
        # Generate explanation
        explanation = self._explain_prediction(feature_set)
        
        return (
            float(risk_scores[0]),
            float(confidence[0]),
            int(anomaly_labels[0]),
            explanation
        )
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate evaluation metrics"""
        return {
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mae': mean_absolute_error(y_true, y_pred),
            'r2': r2_score(y_true, y_pred)
        }
    
    def _calculate_confidence(self, features: np.ndarray, predictions: np.ndarray) -> np.ndarray:
        """Calculate prediction confidence based on model uncertainty"""
        # Use prediction variance from tree ensemble
        if hasattr(self.xgb_model, 'predict'):
            # For XGBoost, we can use the standard deviation of tree predictions
            # This is a simplified confidence measure
            base_confidence = 0.8  # Base confidence
            
            # Adjust confidence based on anomaly detection
            anomaly_scores = self.anomaly_detector.decision_function(features)
            anomaly_confidence = (anomaly_scores + 0.5) / 1.0  # Normalize to 0-1
            anomaly_confidence = np.clip(anomaly_confidence, 0.1, 1.0)
            
            # Combine confidences
            confidence = base_confidence * anomaly_confidence
            
            return np.clip(confidence, 0.1, 1.0)
        
        return np.full(len(predictions), 0.8)
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the model"""
        if not self.is_trained or not self.feature_names:
            return {}
        
        importance = self.xgb_model.feature_importances_
        return dict(zip(self.feature_names, importance.tolist()))
    
    def _explain_prediction(self, feature_set: FeatureSet) -> Dict[str, Any]:
        """Generate explanation for a prediction"""
        if not self.is_trained:
            return {}
        
        # Get feature importance
        feature_importance = self._get_feature_importance()
        
        # Get feature values
        feature_values = dict(zip(feature_set.feature_names, feature_set.features.tolist()))
        
        # Calculate contribution scores
        contributions = {}
        for name, value in feature_values.items():
            if name in feature_importance:
                contributions[name] = {
                    'value': value,
                    'importance': feature_importance[name],
                    'contribution': value * feature_importance[name]
                }
        
        # Sort by contribution
        sorted_contributions = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]['contribution']),
            reverse=True
        )
        
        return {
            'top_factors': sorted_contributions[:10],
            'feature_importance': feature_importance,
            'model_version': self.model_version,
            'explanation_timestamp': datetime.now().isoformat()
        }
    
    def save_model(self) -> None:
        """Save the trained model to disk"""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        model_file = self.model_path / f"risk_model_v{self.model_version}.joblib"
        
        model_data = {
            'xgb_model': self.xgb_model,
            'anomaly_detector': self.anomaly_detector,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_version': self.model_version,
            'training_stats': self.training_stats,
            'is_trained': self.is_trained
        }
        
        joblib.dump(model_data, model_file)
        self.log_event("Model saved", path=str(model_file))
    
    def load_model(self) -> None:
        """Load a trained model from disk"""
        model_file = self.model_path / f"risk_model_v{self.model_version}.joblib"
        
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        
        model_data = joblib.load(model_file)
        
        self.xgb_model = model_data['xgb_model']
        self.anomaly_detector = model_data['anomaly_detector']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.model_version = model_data['model_version']
        self.training_stats = model_data.get('training_stats', {})
        self.is_trained = model_data.get('is_trained', True)
        
        self.log_event("Model loaded", path=str(model_file))
    
    def get_risk_level(self, risk_score: float) -> RiskLevel:
        """Convert risk score to risk level"""
        if risk_score >= 80:
            return RiskLevel.CRITICAL
        elif risk_score >= 60:
            return RiskLevel.HIGH
        elif risk_score >= 30:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def retrain_if_needed(self, features: np.ndarray, targets: np.ndarray, 
                         feature_names: List[str], threshold_days: int = 7) -> bool:
        """Retrain model if it's older than threshold"""
        if not self.training_stats:
            return False
        
        last_training = self.training_stats.get('timestamp')
        if not last_training:
            return False
        
        days_since_training = (datetime.now() - last_training).days
        
        if days_since_training >= threshold_days:
            self.log_event("Retraining model", days_since_training=days_since_training)
            self.train(features, targets, feature_names)
            return True
        
        return False


class SyntheticDataGenerator(LoggerMixin):
    """Generate synthetic training data for the risk scoring model"""
    
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        np.random.seed(random_state)
    
    def generate_training_data(self, n_samples: int = 10000) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Generate synthetic training data"""
        
        self.log_event("Generating synthetic training data", samples=n_samples)
        
        # Feature names (should match FeatureEngineer.feature_names)
        feature_names = [
            'asset_age_days', 'asset_size_log', 'access_frequency_normalized', 'dependency_count_log',
            'exposure_score', 'sensitivity_score', 'criticality_score', 'vulnerability_score',
            'is_repository', 'is_model', 'is_dataset', 'is_document', 'is_code', 'is_api',
            'is_github', 'is_huggingface', 'is_snowflake', 'is_google_drive',
            'days_since_last_access', 'is_recently_accessed', 'is_stale_asset',
            'has_public_exposure', 'has_sensitive_data', 'is_business_critical',
            'cve_count_log', 'severity_score_normalized', 'has_exploit_available', 'threat_actor_count',
            'model_inversion_risk', 'membership_inference_risk', 'data_poisoning_risk',
            'adversarial_attack_risk', 'privacy_leakage_risk',
            'risk_velocity', 'exposure_criticality_interaction', 'age_access_ratio',
            'vulnerability_exposure_product', 'composite_ai_risk'
        ]
        
        n_features = len(feature_names)
        features = np.zeros((n_samples, n_features))
        
        # Generate features with realistic distributions
        for i, name in enumerate(feature_names):
            if 'age_days' in name:
                features[:, i] = np.random.exponential(100, n_samples)
            elif 'log' in name:
                features[:, i] = np.random.exponential(2, n_samples)
            elif 'normalized' in name or 'score' in name or 'risk' in name:
                features[:, i] = np.random.beta(2, 5, n_samples)
            elif name.startswith('is_') or name.startswith('has_'):
                features[:, i] = np.random.binomial(1, 0.3, n_samples)
            elif 'count' in name:
                features[:, i] = np.random.poisson(2, n_samples)
            elif 'ratio' in name or 'interaction' in name or 'product' in name:
                features[:, i] = np.random.gamma(2, 0.5, n_samples)
            else:
                features[:, i] = np.random.normal(0.5, 0.2, n_samples)
        
        # Generate realistic risk scores based on features
        risk_scores = self._generate_realistic_risk_scores(features, feature_names)
        
        # Add noise
        risk_scores += np.random.normal(0, 0.05, n_samples)
        risk_scores = np.clip(risk_scores, 0, 1)
        
        self.log_event("Synthetic data generated", 
                      samples=n_samples, 
                      features=n_features,
                      mean_risk=risk_scores.mean())
        
        return features, risk_scores, feature_names
    
    def _generate_realistic_risk_scores(self, features: np.ndarray, feature_names: List[str]) -> np.ndarray:
        """Generate realistic risk scores based on feature values"""
        
        # Create feature name to index mapping
        name_to_idx = {name: i for i, name in enumerate(feature_names)}
        
        # Base risk calculation
        base_risk = (
            0.3 * features[:, name_to_idx['vulnerability_score']] +
            0.2 * features[:, name_to_idx['exposure_score']] +
            0.2 * features[:, name_to_idx['criticality_score']] +
            0.1 * features[:, name_to_idx['sensitivity_score']] +
            0.1 * features[:, name_to_idx['composite_ai_risk']] +
            0.1 * features[:, name_to_idx['severity_score_normalized']]
        )
        
        # Adjust for asset type
        type_multipliers = {
            'is_model': 1.2,
            'is_dataset': 1.1,
            'is_repository': 1.0,
            'is_api': 1.3,
            'is_document': 0.8,
            'is_code': 0.9
        }
        
        for type_name, multiplier in type_multipliers.items():
            if type_name in name_to_idx:
                mask = features[:, name_to_idx[type_name]] == 1
                base_risk[mask] *= multiplier
        
        # Adjust for public exposure
        if 'has_public_exposure' in name_to_idx:
            public_mask = features[:, name_to_idx['has_public_exposure']] == 1
            base_risk[public_mask] *= 1.5
        
        # Adjust for stale assets
        if 'is_stale_asset' in name_to_idx:
            stale_mask = features[:, name_to_idx['is_stale_asset']] == 1
            base_risk[stale_mask] *= 1.2
        
        return np.clip(base_risk, 0, 1)