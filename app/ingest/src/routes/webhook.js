import express from 'express';
import crypto from 'crypto';
import { config } from '../config/index.js';
import { logger } from '../utils/logger.js';
import { publishEvent } from '../services/kafka.js';
import { isDuplicateEvent } from '../services/redis.js';
import { validateWebhookPayload } from '../middleware/validation.js';

export const webhookRouter = express.Router();

// `uuid` package in this repo isn't consistently exporting `v7`.
// For MVP ingestion we just need stable unique IDs; Node 18+ provides this.
const uuidv7 = () => crypto.randomUUID();

// Webhook signature verification middleware
const verifySignature = (secret) => (req, res, next) => {
  const signature = req.headers['x-hub-signature-256'] || req.headers['x-signature'];
  
  if (!signature) {
    return res.status(401).json({ error: 'Missing signature' });
  }

  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(JSON.stringify(req.body));
  const expectedSignature = `sha256=${hmac.digest('hex')}`;

  if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedSignature))) {
    logger.warn('Invalid webhook signature', { 
      ip: req.ip,
      userAgent: req.get('User-Agent')
    });
    return res.status(401).json({ error: 'Invalid signature' });
  }

  next();
};

// GitHub webhook handler
webhookRouter.post('/github', 
  verifySignature(config.webhooks.github),
  validateWebhookPayload,
  async (req, res) => {
    try {
      const eventType = req.headers['x-github-event'];
      const deliveryId = req.headers['x-github-delivery'];
      
      // Check for duplicate events
      if (await isDuplicateEvent(deliveryId)) {
        logger.info('Duplicate GitHub event ignored', { deliveryId, eventType });
        return res.status(200).json({ status: 'duplicate' });
      }

      const event = {
        id: uuidv7(),
        vendor: 'github',
        type: eventType,
        deliveryId,
        repository: req.body.repository?.full_name,
        actor: req.body.sender?.login,
        action: req.body.action,
        timestamp: new Date().toISOString(),
        payload: req.body,
        traceId: req.headers['x-trace-id'] || uuidv7()
      };

      // Infer asset information
      if (eventType === 'push') {
        event.assetHint = {
          type: 'repository',
          files: req.body.commits?.flatMap(c => c.added.concat(c.modified)) || []
        };
      } else if (eventType === 'release') {
        event.assetHint = {
          type: 'release',
          version: req.body.release?.tag_name
        };
      }

      await publishEvent(config.kafka.topics.events, event);

      logger.info('GitHub webhook processed', {
        eventType,
        repository: event.repository,
        actor: event.actor,
        eventId: event.id
      });

      res.status(200).json({ 
        status: 'processed',
        eventId: event.id 
      });

    } catch (error) {
      logger.error('GitHub webhook processing failed', {
        error: error.message,
        deliveryId: req.headers['x-github-delivery']
      });
      res.status(500).json({ error: 'Processing failed' });
    }
  }
);

// HuggingFace webhook handler
webhookRouter.post('/huggingface',
  verifySignature(config.webhooks.hmacSecret),
  validateWebhookPayload,
  async (req, res) => {
    try {
      const eventId = uuidv7();
      
      if (await isDuplicateEvent(eventId)) {
        return res.status(200).json({ status: 'duplicate' });
      }

      const event = {
        id: eventId,
        vendor: 'huggingface',
        type: req.body.event_type || 'model.updated',
        modelId: req.body.repo?.name,
        actor: req.body.repo?.owner,
        timestamp: new Date().toISOString(),
        payload: req.body,
        assetHint: {
          type: 'model',
          framework: req.body.repo?.library_name
        },
        traceId: req.headers['x-trace-id'] || eventId
      };

      await publishEvent(config.kafka.topics.events, event);

      logger.info('HuggingFace webhook processed', {
        modelId: event.modelId,
        eventId: event.id
      });

      res.status(200).json({ 
        status: 'processed',
        eventId: event.id 
      });

    } catch (error) {
      logger.error('HuggingFace webhook processing failed', {
        error: error.message
      });
      res.status(500).json({ error: 'Processing failed' });
    }
  }
);

// Generic webhook handler for other sources
webhookRouter.post('/generic',
  verifySignature(config.webhooks.hmacSecret),
  validateWebhookPayload,
  async (req, res) => {
    try {
      const eventId = uuidv7();
      const vendor = req.headers['x-vendor'] || 'unknown';
      
      if (await isDuplicateEvent(eventId)) {
        return res.status(200).json({ status: 'duplicate' });
      }

      const event = {
        id: eventId,
        vendor,
        type: req.body.event_type || 'generic.event',
        timestamp: new Date().toISOString(),
        payload: req.body,
        traceId: req.headers['x-trace-id'] || eventId
      };

      await publishEvent(config.kafka.topics.events, event);

      logger.info('Generic webhook processed', {
        vendor,
        eventId: event.id
      });

      res.status(200).json({ 
        status: 'processed',
        eventId: event.id 
      });

    } catch (error) {
      logger.error('Generic webhook processing failed', {
        error: error.message
      });
      res.status(500).json({ error: 'Processing failed' });
    }
  }
);