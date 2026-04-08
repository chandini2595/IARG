"""
Configuration settings for the Risk Scoring Service
"""

import json
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    debug: bool = False
    environment: str = "development"
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8002
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    allowed_hosts: List[str] = ["*"]
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password123"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_password: str = ""
    redis_key_prefix: str = "iarg:score:"
    redis_ttl: int = 3600  # 1 hour
    
    # Kafka
    # Keep as plain string to avoid pydantic-settings JSON parsing errors.
    # Expected examples:
    # - "kafka:29092"
    # - "kafka:29092,localhost:9092"
    # - '["kafka:29092"]'
    kafka_brokers: str = "localhost:9092"
    kafka_consumer_group: str = "iarg-risk-scorer"
    kafka_topics: dict = {
        "events": "iarg.events",
        "asset_discovered": "iarg.asset.discovered",
        "risk_score": "iarg.risk.score"
    }
    
    # Risk Scoring
    risk_score_threshold: float = 70.0
    risk_factors: dict = {
        "exposure_weight": 0.3,
        "frequency_weight": 0.2,
        "vulnerability_weight": 0.3,
        "ai_factors_weight": 0.2
    }
    
    # ML Models
    model_path: str = "models/"
    model_update_interval: int = 3600  # 1 hour
    
    # External APIs
    threat_intel_api_key: str = ""
    threat_intel_base_url: str = "https://api.threatintel.example.com"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def kafka_brokers_list(self) -> List[str]:
        s = (self.kafka_brokers or "").strip()
        if not s:
            return []

        # Try JSON array first.
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass

        # Fallback: comma-separated / single broker.
        return [part.strip() for part in s.split(",") if part.strip()]


# Global settings instance
settings = Settings()