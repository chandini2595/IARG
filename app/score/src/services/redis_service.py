"""
Redis service for caching and session management
"""

import json
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from src.utils.logging import LoggerMixin


class RedisService(LoggerMixin):
    """Redis service for caching and data storage"""
    
    def __init__(self, redis_url: str, password: Optional[str] = None):
        self.redis_url = redis_url
        self.password = password
        self.client: Optional[redis.Redis] = None
        self.key_prefix = "iarg:score:"
    
    async def connect(self) -> None:
        """Connect to Redis"""
        try:
            self.client = redis.from_url(
                self.redis_url,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            await self.ping()
            self.log_event("Connected to Redis", url=self.redis_url)
            
        except Exception as e:
            self.log_error(e, {"component": "redis_connection"})
            raise
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self.log_event("Redis connection closed")
    
    async def ping(self) -> bool:
        """Ping Redis to check connection"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        result = await self.client.ping()
        return result
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        full_key = f"{self.key_prefix}{key}"
        return await self.client.get(full_key)
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set key-value pair"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        full_key = f"{self.key_prefix}{key}"
        return await self.client.set(full_key, value, ex=ttl)
    
    async def setex(self, key: str, ttl: int, value: str) -> bool:
        """Set key-value pair with expiration"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        full_key = f"{self.key_prefix}{key}"
        return await self.client.setex(full_key, ttl, value)
    
    async def delete(self, key: str) -> int:
        """Delete key"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        full_key = f"{self.key_prefix}{key}"
        return await self.client.delete(full_key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        full_key = f"{self.key_prefix}{key}"
        return bool(await self.client.exists(full_key))
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        full_key = f"{self.key_prefix}{key}"
        return await self.client.incrby(full_key, amount)
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        full_key = f"{self.key_prefix}{key}"
        return await self.client.expire(full_key, ttl)
    
    # Specialized methods for risk scoring
    
    async def cache_risk_score(self, asset_id: str, risk_score_data: Dict[str, Any], 
                              ttl: int = 3600) -> bool:
        """Cache risk score data"""
        try:
            key = f"risk_score:{asset_id}"
            value = json.dumps(risk_score_data, default=str)
            return await self.setex(key, ttl, value)
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "cache_risk_score"})
            return False
    
    async def get_cached_risk_score(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get cached risk score data"""
        try:
            key = f"risk_score:{asset_id}"
            cached_data = await self.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "get_cached_risk_score"})
            return None
    
    async def increment_access_count(self, asset_id: str) -> int:
        """Increment access count for an asset"""
        try:
            # Daily access count
            today = datetime.now().strftime("%Y-%m-%d")
            daily_key = f"access_count:daily:{asset_id}:{today}"
            daily_count = await self.increment(daily_key)
            
            # Set expiration for daily counter (keep for 30 days)
            await self.expire(daily_key, 30 * 24 * 3600)
            
            # Total access count
            total_key = f"access_count:total:{asset_id}"
            total_count = await self.increment(total_key)
            
            return total_count
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "increment_access_count"})
            return 0
    
    async def get_access_count(self, asset_id: str, days: int = 30) -> int:
        """Get access count for an asset over specified days"""
        try:
            total_count = 0
            
            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                daily_key = f"access_count:daily:{asset_id}:{date}"
                
                count_str = await self.get(daily_key)
                if count_str:
                    total_count += int(count_str)
            
            return total_count
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "days": days, "component": "get_access_count"})
            return 0
    
    async def cache_threat_intelligence(self, asset_id: str, threat_data: Dict[str, Any], 
                                      ttl: int = 21600) -> bool:  # 6 hours default
        """Cache threat intelligence data"""
        try:
            key = f"threat_intel:{asset_id}"
            value = json.dumps(threat_data, default=str)
            return await self.setex(key, ttl, value)
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "cache_threat_intelligence"})
            return False
    
    async def get_cached_threat_intelligence(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get cached threat intelligence data"""
        try:
            key = f"threat_intel:{asset_id}"
            cached_data = await self.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "get_cached_threat_intelligence"})
            return None
    
    async def store_model_metrics(self, model_version: str, metrics: Dict[str, Any]) -> bool:
        """Store ML model performance metrics"""
        try:
            key = f"model_metrics:{model_version}"
            value = json.dumps(metrics, default=str)
            # Keep model metrics for 30 days
            return await self.setex(key, 30 * 24 * 3600, value)
        except Exception as e:
            self.log_error(e, {"model_version": model_version, "component": "store_model_metrics"})
            return False
    
    async def get_model_metrics(self, model_version: str) -> Optional[Dict[str, Any]]:
        """Get ML model performance metrics"""
        try:
            key = f"model_metrics:{model_version}"
            cached_data = await self.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            self.log_error(e, {"model_version": model_version, "component": "get_model_metrics"})
            return None
    
    async def store_feature_importance(self, model_version: str, 
                                     feature_importance: Dict[str, float]) -> bool:
        """Store feature importance data"""
        try:
            key = f"feature_importance:{model_version}"
            value = json.dumps(feature_importance)
            # Keep feature importance for 30 days
            return await self.setex(key, 30 * 24 * 3600, value)
        except Exception as e:
            self.log_error(e, {"model_version": model_version, "component": "store_feature_importance"})
            return False
    
    async def get_feature_importance(self, model_version: str) -> Optional[Dict[str, float]]:
        """Get feature importance data"""
        try:
            key = f"feature_importance:{model_version}"
            cached_data = await self.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            self.log_error(e, {"model_version": model_version, "component": "get_feature_importance"})
            return None
    
    async def set_last_score_time(self, asset_id: str, timestamp: datetime) -> bool:
        """Set last scoring time for an asset"""
        try:
            key = f"last_score_time:{asset_id}"
            value = timestamp.isoformat()
            # Keep for 7 days
            return await self.setex(key, 7 * 24 * 3600, value)
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "set_last_score_time"})
            return False
    
    async def get_last_score_time(self, asset_id: str) -> Optional[datetime]:
        """Get last scoring time for an asset"""
        try:
            key = f"last_score_time:{asset_id}"
            timestamp_str = await self.get(key)
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
            return None
        except Exception as e:
            self.log_error(e, {"asset_id": asset_id, "component": "get_last_score_time"})
            return None
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            if not self.client:
                return {}
            
            info = await self.client.info()
            
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            self.log_error(e, {"component": "get_cache_statistics"})
            return {}