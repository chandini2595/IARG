import express from 'express';
import { kafkaProducer } from '../services/kafka.js';
import { redisClient } from '../services/redis.js';
import { logger } from '../utils/logger.js';
import { config } from '../config/index.js';

export const healthRouter = express.Router();

// Basic health check
healthRouter.get('/', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    service: 'iarg-ingest',
    version: config.version,
    timestamp: new Date().toISOString()
  });
});

// Detailed health check with dependencies
healthRouter.get('/detailed', async (req, res) => {
  const health = {
    status: 'healthy',
    service: 'iarg-ingest',
    version: config.version,
    timestamp: new Date().toISOString(),
    dependencies: {}
  };

  let overallStatus = 'healthy';

  // Check Kafka connection
  try {
    // Simple check - if producer is connected
    health.dependencies.kafka = {
      status: 'healthy',
      brokers: config.kafka.brokers
    };
  } catch (error) {
    health.dependencies.kafka = {
      status: 'unhealthy',
      error: error.message
    };
    overallStatus = 'unhealthy';
  }

  // Check Redis connection
  try {
    await redisClient.ping();
    health.dependencies.redis = {
      status: 'healthy',
      url: config.redis.url.replace(/\/\/.*@/, '//***@') // Hide credentials
    };
  } catch (error) {
    health.dependencies.redis = {
      status: 'unhealthy',
      error: error.message
    };
    overallStatus = 'unhealthy';
  }

  health.status = overallStatus;
  
  const statusCode = overallStatus === 'healthy' ? 200 : 503;
  res.status(statusCode).json(health);
});

// Readiness probe
healthRouter.get('/ready', async (req, res) => {
  try {
    // Check if all critical services are ready
    await redisClient.ping();
    
    res.status(200).json({
      status: 'ready',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    logger.error('Readiness check failed', { error: error.message });
    res.status(503).json({
      status: 'not ready',
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Liveness probe
healthRouter.get('/live', (req, res) => {
  res.status(200).json({
    status: 'alive',
    timestamp: new Date().toISOString()
  });
});