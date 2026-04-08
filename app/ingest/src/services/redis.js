import { createClient } from 'redis';
import { config } from '../config/index.js';
import { logger } from '../utils/logger.js';

export const redisClient = createClient({
  url: config.redis.url,
  password: config.redis.password,
  socket: {
    reconnectStrategy: (retries) => Math.min(retries * 50, 500)
  }
});

redisClient.on('error', (error) => {
  logger.error('Redis client error:', error);
});

redisClient.on('connect', () => {
  logger.info('Redis client connected');
});

redisClient.on('reconnecting', () => {
  logger.warn('Redis client reconnecting');
});

// Cache utilities
export const cacheSet = async (key, value, ttl = config.redis.ttl.default) => {
  try {
    const prefixedKey = `${config.redis.keyPrefix}${key}`;
    await redisClient.setEx(prefixedKey, ttl, JSON.stringify(value));
    return true;
  } catch (error) {
    logger.error('Cache set error:', { key, error: error.message });
    return false;
  }
};

export const cacheGet = async (key) => {
  try {
    const prefixedKey = `${config.redis.keyPrefix}${key}`;
    const value = await redisClient.get(prefixedKey);
    return value ? JSON.parse(value) : null;
  } catch (error) {
    logger.error('Cache get error:', { key, error: error.message });
    return null;
  }
};

export const cacheDel = async (key) => {
  try {
    const prefixedKey = `${config.redis.keyPrefix}${key}`;
    await redisClient.del(prefixedKey);
    return true;
  } catch (error) {
    logger.error('Cache delete error:', { key, error: error.message });
    return false;
  }
};

export const cacheExists = async (key) => {
  try {
    const prefixedKey = `${config.redis.keyPrefix}${key}`;
    const exists = await redisClient.exists(prefixedKey);
    return exists === 1;
  } catch (error) {
    logger.error('Cache exists error:', { key, error: error.message });
    return false;
  }
};

// Event deduplication
export const isDuplicateEvent = async (eventId, ttl = config.redis.ttl.events) => {
  const key = `event:${eventId}`;
  const exists = await cacheExists(key);
  
  if (!exists) {
    await cacheSet(key, { processed: true }, ttl);
    return false;
  }
  
  return true;
};