import { Kafka } from 'kafkajs';
import { config } from '../config/index.js';
import { logger } from '../utils/logger.js';

const kafka = new Kafka({
  clientId: config.kafka.clientId,
  brokers: config.kafka.brokers,
  retry: {
    initialRetryTime: 100,
    retries: 8
  }
});

export const kafkaProducer = kafka.producer({
  maxInFlightRequests: 1,
  idempotent: true,
  transactionTimeout: 30000
});

// Event publishing utility
export const publishEvent = async (topic, event) => {
  try {
    const message = {
      key: event.id || event.assetId,
      value: JSON.stringify({
        ...event,
        timestamp: new Date().toISOString(),
        version: '1.0'
      }),
      headers: {
        'content-type': 'application/json',
        'event-type': event.type,
        'trace-id': event.traceId || 'unknown'
      }
    };

    await kafkaProducer.send({
      topic,
      messages: [message]
    });

    logger.info('Event published successfully', {
      topic,
      eventId: event.id,
      eventType: event.type
    });

    return true;
  } catch (error) {
    logger.error('Failed to publish event', {
      topic,
      eventId: event.id,
      error: error.message
    });
    throw error;
  }
};

// Specific event publishers
export const publishAssetDiscovered = (event) => 
  publishEvent(config.kafka.topics.assetDiscovered, {
    ...event,
    type: 'asset.discovered.v1'
  });

export const publishRiskScore = (event) => 
  publishEvent(config.kafka.topics.riskScore, {
    ...event,
    type: 'risk.score.v1'
  });

export const publishValuation = (event) => 
  publishEvent(config.kafka.topics.valuation, {
    ...event,
    type: 'valuation.completed.v1'
  });

export const publishPolicyEvent = (event) => 
  publishEvent(config.kafka.topics.policy, {
    ...event,
    type: 'policy.bound.v1'
  });