import Joi from 'joi';
import { logger } from '../utils/logger.js';

// GitHub webhook payload schema
const githubWebhookSchema = Joi.object({
  action: Joi.string(),
  repository: Joi.object({
    id: Joi.number().required(),
    name: Joi.string().required(),
    full_name: Joi.string().required(),
    owner: Joi.object({
      login: Joi.string().required(),
      id: Joi.number().required()
    }).required(),
    private: Joi.boolean(),
    html_url: Joi.string().uri(),
    description: Joi.string().allow(null),
    created_at: Joi.string(),
    updated_at: Joi.string(),
    language: Joi.string().allow(null),
    size: Joi.number(),
    default_branch: Joi.string()
  }),
  sender: Joi.object({
    login: Joi.string().required(),
    id: Joi.number().required(),
    type: Joi.string()
  }),
  commits: Joi.array().items(
    Joi.object({
      id: Joi.string().required(),
      message: Joi.string().required(),
      author: Joi.object({
        name: Joi.string(),
        email: Joi.string().email()
      }),
      added: Joi.array().items(Joi.string()),
      modified: Joi.array().items(Joi.string()),
      removed: Joi.array().items(Joi.string())
    })
  ),
  head_commit: Joi.object(),
  ref: Joi.string(),
  before: Joi.string(),
  after: Joi.string()
}).unknown(true); // Allow additional fields

// HuggingFace webhook payload schema
const huggingfaceWebhookSchema = Joi.object({
  event_type: Joi.string(),
  repo: Joi.object({
    name: Joi.string().required(),
    owner: Joi.string(),
    library_name: Joi.string(),
    type: Joi.string()
  }),
  webhook: Joi.object(),
  discussion: Joi.object()
}).unknown(true);

// Generic webhook payload schema
const genericWebhookSchema = Joi.object({
  event_type: Joi.string(),
  timestamp: Joi.string(),
  data: Joi.object()
}).unknown(true);

export const validateWebhookPayload = (req, res, next) => {
  const vendor = req.path.includes('github') ? 'github' : 
                req.path.includes('huggingface') ? 'huggingface' : 'generic';
  
  let schema;
  switch (vendor) {
    case 'github':
      schema = githubWebhookSchema;
      break;
    case 'huggingface':
      schema = huggingfaceWebhookSchema;
      break;
    default:
      schema = genericWebhookSchema;
  }

  const { error, value } = schema.validate(req.body, {
    allowUnknown: true,
    stripUnknown: false
  });

  if (error) {
    logger.warn('Webhook payload validation failed', {
      vendor,
      error: error.details,
      path: req.path
    });
    
    return res.status(400).json({
      error: 'Invalid payload',
      details: error.details.map(d => ({
        field: d.path.join('.'),
        message: d.message
      }))
    });
  }

  req.body = value;
  next();
};

// Asset metadata validation
export const assetMetadataSchema = Joi.object({
  id: Joi.string().required(),
  type: Joi.string().valid('repository', 'model', 'dataset', 'document', 'code').required(),
  name: Joi.string().required(),
  owner: Joi.string().required(),
  source: Joi.string().valid('github', 'huggingface', 'snowflake', 'google_drive').required(),
  metadata: Joi.object({
    size: Joi.number(),
    language: Joi.string(),
    framework: Joi.string(),
    tags: Joi.array().items(Joi.string()),
    description: Joi.string(),
    created_at: Joi.string(),
    updated_at: Joi.string(),
    access_level: Joi.string().valid('public', 'private', 'internal')
  }),
  dependencies: Joi.array().items(Joi.string()),
  risk_factors: Joi.object({
    exposure: Joi.number().min(0).max(1),
    sensitivity: Joi.number().min(0).max(1),
    criticality: Joi.number().min(0).max(1)
  })
});

export const validateAssetMetadata = (req, res, next) => {
  const { error, value } = assetMetadataSchema.validate(req.body);

  if (error) {
    return res.status(400).json({
      error: 'Invalid asset metadata',
      details: error.details.map(d => ({
        field: d.path.join('.'),
        message: d.message
      }))
    });
  }

  req.body = value;
  next();
};