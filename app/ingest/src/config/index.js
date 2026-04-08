import dotenv from 'dotenv';

dotenv.config();

export const config = {
  env: process.env.NODE_ENV || 'development',
  port: parseInt(process.env.PORT) || 3001,
  version: process.env.npm_package_version || '1.0.0',
  
  // CORS configuration
  cors: {
    origins: process.env.CORS_ORIGINS?.split(',') || ['http://localhost:3000']
  },

  // Kafka configuration
  kafka: {
    brokers: process.env.KAFKA_BROKERS?.split(',') || ['localhost:9092'],
    clientId: 'iarg-ingest',
    topics: {
      events: 'iarg.events',
      assetDiscovered: 'iarg.asset.discovered',
      riskScore: 'iarg.risk.score',
      valuation: 'iarg.valuation',
      policy: 'iarg.policy'
    }
  },

  // Redis configuration
  redis: {
    url: process.env.REDIS_URL || 'redis://localhost:6379',
    password: process.env.REDIS_PASSWORD,
    keyPrefix: 'iarg:',
    ttl: {
      default: 3600, // 1 hour
      events: 86400, // 24 hours
      cache: 1800    // 30 minutes
    }
  },

  // Webhook secrets
  webhooks: {
    github: process.env.GITHUB_WEBHOOK_SECRET,
    stripe: process.env.STRIPE_WEBHOOK_SECRET,
    hmacSecret: process.env.HMAC_SECRET || 'default-hmac-secret'
  },

  // External APIs
  apis: {
    github: {
      token: process.env.GITHUB_TOKEN,
      baseUrl: 'https://api.github.com'
    },
    huggingface: {
      token: process.env.HUGGINGFACE_TOKEN,
      baseUrl: 'https://huggingface.co/api'
    },
    snowflake: {
      account: process.env.SNOWFLAKE_ACCOUNT,
      username: process.env.SNOWFLAKE_USERNAME,
      password: process.env.SNOWFLAKE_PASSWORD
    }
  },

  // Logging
  logging: {
    level: process.env.LOG_LEVEL || 'info',
    format: process.env.LOG_FORMAT || 'json'
  },

  // Rate limiting
  rateLimit: {
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100 // limit each IP to 100 requests per windowMs
  }
};