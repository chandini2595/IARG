"""
IARG Risk Scoring Service
Main FastAPI application for AI-driven risk assessment
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from src.config import settings
from src.api.routes import router, set_services
from src.services.kafka_service import KafkaService
from src.services.neo4j_service import Neo4jService
from src.services.redis_service import RedisService
from src.services.risk_scorer import RiskScoringService
from src.utils.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global service instances
kafka_service: KafkaService = None
neo4j_service: Neo4jService = None
redis_service: RedisService = None
risk_scorer: RiskScoringService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global kafka_service, neo4j_service, redis_service, risk_scorer
    
    logger.info("Starting IARG Risk Scoring Service")
    
    try:
        # Initialize services
        neo4j_service = Neo4jService(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
        await neo4j_service.connect()
        
        redis_service = RedisService(settings.redis_url, settings.redis_password)
        await redis_service.connect()
        
        kafka_service = KafkaService(settings.kafka_brokers_list)
        await kafka_service.connect()
        
        risk_scorer = RiskScoringService(neo4j_service, redis_service)
        await risk_scorer.initialize()
        
        # Set services in routes module
        set_services(risk_scorer, neo4j_service, redis_service)
        
        # Start Kafka consumer
        consumer_task = asyncio.create_task(
            kafka_service.start_consumer(risk_scorer.process_event)
        )
        
        logger.info("All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down services")
        
        if kafka_service:
            await kafka_service.close()
        if neo4j_service:
            await neo4j_service.close()
        if redis_service:
            await redis_service.close()
        
        logger.info("Services shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="IARG Risk Scoring Service",
    description="AI-driven risk assessment for intangible assets",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts
)

# Include routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "IARG Risk Scoring Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": "iarg-score",
        "version": "1.0.0"
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with dependencies"""
    health_status = {
        "status": "healthy",
        "service": "iarg-score",
        "version": "1.0.0",
        "dependencies": {}
    }
    
    overall_healthy = True
    
    # Check Neo4j
    try:
        if neo4j_service:
            await neo4j_service.health_check()
            health_status["dependencies"]["neo4j"] = {"status": "healthy"}
        else:
            health_status["dependencies"]["neo4j"] = {"status": "not_initialized"}
            overall_healthy = False
    except Exception as e:
        health_status["dependencies"]["neo4j"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Check Redis
    try:
        if redis_service:
            await redis_service.ping()
            health_status["dependencies"]["redis"] = {"status": "healthy"}
        else:
            health_status["dependencies"]["redis"] = {"status": "not_initialized"}
            overall_healthy = False
    except Exception as e:
        health_status["dependencies"]["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Check Kafka
    try:
        if kafka_service:
            health_status["dependencies"]["kafka"] = {"status": "healthy"}
        else:
            health_status["dependencies"]["kafka"] = {"status": "not_initialized"}
            overall_healthy = False
    except Exception as e:
        health_status["dependencies"]["kafka"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    if not overall_healthy:
        health_status["status"] = "unhealthy"
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8002,
        reload=settings.debug,
        log_level="info"
    )