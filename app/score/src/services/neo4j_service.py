"""
Neo4j service for the risk scoring service
"""

from typing import Dict, List, Optional, Any
from neo4j import AsyncGraphDatabase, AsyncDriver
from datetime import datetime

from src.utils.logging import LoggerMixin


class Neo4jService(LoggerMixin):
    """Neo4j service for asset data retrieval"""
    
    def __init__(self, uri: str, username: str, password: str):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver: Optional[AsyncDriver] = None
    
    async def connect(self) -> None:
        """Connect to Neo4j database"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            
            # Test connection
            await self.health_check()
            self.log_event("Connected to Neo4j", uri=self.uri)
            
        except Exception as e:
            self.log_error(e, {"component": "neo4j_connection"})
            raise
    
    async def close(self) -> None:
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
            self.log_event("Neo4j connection closed")
    
    async def health_check(self) -> None:
        """Check Neo4j connection health"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        async with self.driver.session() as session:
            result = await session.run("RETURN 1 as health")
            record = await result.single()
            if not record or record["health"] != 1:
                raise RuntimeError("Neo4j health check failed")
    
    async def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get asset data by ID"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH (a:Asset {id: $asset_id})
        RETURN a {
            .id, .type, .name, .owner, .source, .description,
            .metadata, .created_at, .updated_at, .last_accessed,
            .tags, .status
        } as asset
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, asset_id=asset_id)
            record = await result.single()
            
            if record:
                asset_data = record["asset"]
                # Convert datetime strings back to datetime objects
                if asset_data.get("created_at"):
                    asset_data["created_at"] = self._parse_datetime(asset_data["created_at"])
                if asset_data.get("updated_at"):
                    asset_data["updated_at"] = self._parse_datetime(asset_data["updated_at"])
                if asset_data.get("last_accessed"):
                    asset_data["last_accessed"] = self._parse_datetime(asset_data["last_accessed"])
                
                return asset_data
            
            return None
    
    async def get_dependency_count(self, asset_id: str) -> int:
        """Get the number of dependencies for an asset"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH (a:Asset {id: $asset_id})-[:DEPENDS_ON]->()
        RETURN count(*) as dependency_count
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, asset_id=asset_id)
            record = await result.single()
            return record["dependency_count"] if record else 0
    
    async def get_dependent_count(self, asset_id: str) -> int:
        """Get the number of assets that depend on this asset"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH ()-[:DEPENDS_ON]->(a:Asset {id: $asset_id})
        RETURN count(*) as dependent_count
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, asset_id=asset_id)
            record = await result.single()
            return record["dependent_count"] if record else 0
    
    async def get_asset_lineage(self, asset_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get asset lineage (dependencies and dependents)"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH path = (a:Asset {id: $asset_id})-[:DEPENDS_ON*1..$depth]->()
        WITH collect(path) as downstream_paths
        
        MATCH path = ()-[:DEPENDS_ON*1..$depth]->(a:Asset {id: $asset_id})
        WITH downstream_paths, collect(path) as upstream_paths
        
        RETURN {
            downstream: downstream_paths,
            upstream: upstream_paths
        } as lineage
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, asset_id=asset_id, depth=depth)
            record = await result.single()
            return record["lineage"] if record else {"downstream": [], "upstream": []}
    
    async def get_assets_by_type(self, asset_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get assets by type"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH (a:Asset {type: $asset_type})
        WHERE a.status <> 'deleted'
        RETURN a {
            .id, .type, .name, .owner, .source, .description,
            .metadata, .created_at, .updated_at, .last_accessed,
            .tags, .status
        } as asset
        ORDER BY a.updated_at DESC
        LIMIT $limit
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, asset_type=asset_type, limit=limit)
            assets = []
            
            async for record in result:
                asset_data = record["asset"]
                # Convert datetime strings
                if asset_data.get("created_at"):
                    asset_data["created_at"] = self._parse_datetime(asset_data["created_at"])
                if asset_data.get("updated_at"):
                    asset_data["updated_at"] = self._parse_datetime(asset_data["updated_at"])
                if asset_data.get("last_accessed"):
                    asset_data["last_accessed"] = self._parse_datetime(asset_data["last_accessed"])
                
                assets.append(asset_data)
            
            return assets
    
    async def get_high_risk_assets(self, risk_threshold: float = 70.0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get assets with high risk scores"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH (a:Asset)
        WHERE a.risk_score >= $risk_threshold AND a.status <> 'deleted'
        RETURN a {
            .id, .type, .name, .owner, .source, .risk_score,
            .updated_at, .status
        } as asset
        ORDER BY a.risk_score DESC
        LIMIT $limit
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, risk_threshold=risk_threshold, limit=limit)
            assets = []
            
            async for record in result:
                asset_data = record["asset"]
                if asset_data.get("updated_at"):
                    asset_data["updated_at"] = self._parse_datetime(asset_data["updated_at"])
                assets.append(asset_data)
            
            return assets
    
    async def update_asset_risk_score(self, asset_id: str, risk_score: float, 
                                    risk_level: str, timestamp: datetime) -> None:
        """Update asset risk score in Neo4j"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH (a:Asset {id: $asset_id})
        SET a.risk_score = $risk_score,
            a.risk_level = $risk_level,
            a.risk_updated_at = $timestamp
        RETURN a.id as updated_id
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                query,
                asset_id=asset_id,
                risk_score=risk_score,
                risk_level=risk_level,
                timestamp=timestamp
            )
            record = await result.single()
            
            if not record:
                self.log_event("Asset not found for risk score update", asset_id=asset_id)
            else:
                self.log_event("Asset risk score updated", 
                             asset_id=asset_id, 
                             risk_score=risk_score)
    
    async def get_asset_statistics(self) -> Dict[str, Any]:
        """Get asset statistics for monitoring"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        query = """
        MATCH (a:Asset)
        WHERE a.status <> 'deleted'
        WITH a
        RETURN {
            total_assets: count(a),
            by_type: apoc.map.groupByMulti(collect({type: a.type}), 'type'),
            by_source: apoc.map.groupByMulti(collect({source: a.source}), 'source'),
            avg_risk_score: avg(a.risk_score),
            high_risk_count: count(CASE WHEN a.risk_score >= 70 THEN 1 END),
            medium_risk_count: count(CASE WHEN a.risk_score >= 30 AND a.risk_score < 70 THEN 1 END),
            low_risk_count: count(CASE WHEN a.risk_score < 30 THEN 1 END)
        } as stats
        """
        
        async with self.driver.session() as session:
            result = await session.run(query)
            record = await result.single()
            return record["stats"] if record else {}
    
    def _parse_datetime(self, dt_value: Any) -> datetime:
        """Parse datetime value from Neo4j"""
        if isinstance(dt_value, datetime):
            return dt_value
        elif isinstance(dt_value, str):
            try:
                return datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            except ValueError:
                return datetime.now()
        else:
            return datetime.now()