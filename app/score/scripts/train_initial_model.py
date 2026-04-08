#!/usr/bin/env python3
"""
Script to train the initial risk scoring model with synthetic data
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.services.ml_models import RiskScoringModel, SyntheticDataGenerator
from src.utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def main():
    """Train initial model with synthetic data"""
    logger.info("Starting initial model training")
    
    try:
        # Create models directory
        models_dir = Path(__file__).parent.parent / "models"
        models_dir.mkdir(exist_ok=True)
        
        # Initialize components
        model = RiskScoringModel(str(models_dir))
        generator = SyntheticDataGenerator()
        
        # Generate synthetic training data
        logger.info("Generating synthetic training data...")
        features, targets, feature_names = generator.generate_training_data(10000)
        
        logger.info(f"Generated {len(features)} samples with {len(feature_names)} features")
        logger.info(f"Target range: {targets.min():.3f} - {targets.max():.3f}")
        logger.info(f"Target mean: {targets.mean():.3f}")
        
        # Train the model
        logger.info("Training XGBoost model...")
        training_stats = model.train(features, targets, feature_names)
        
        # Print training results
        logger.info("Training completed!")
        logger.info(f"Training RMSE: {training_stats['train_metrics']['rmse']:.4f}")
        logger.info(f"Validation RMSE: {training_stats['val_metrics']['rmse']:.4f}")
        logger.info(f"Training R²: {training_stats['train_metrics']['r2']:.4f}")
        logger.info(f"Validation R²: {training_stats['val_metrics']['r2']:.4f}")
        logger.info(f"CV RMSE: {training_stats['cv_rmse_mean']:.4f} ± {training_stats['cv_rmse_std']:.4f}")
        
        # Print top feature importance
        feature_importance = training_stats['feature_importance']
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        
        logger.info("Top 10 most important features:")
        for i, (feature, importance) in enumerate(top_features, 1):
            logger.info(f"  {i:2d}. {feature:<30} {importance:.4f}")
        
        logger.info(f"Model saved successfully to {models_dir}")
        
    except Exception as e:
        logger.error(f"Error training model: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())