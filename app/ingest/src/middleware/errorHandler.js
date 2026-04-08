import { logger } from '../utils/logger.js';

export const errorHandler = (error, req, res, next) => {
  // Log the error
  logger.error('Unhandled error', {
    error: error.message,
    stack: error.stack,
    path: req.path,
    method: req.method,
    ip: req.ip,
    userAgent: req.get('User-Agent'),
    traceId: req.headers['x-trace-id']
  });

  // Don't expose internal errors in production
  const isDevelopment = process.env.NODE_ENV === 'development';
  
  let statusCode = 500;
  let message = 'Internal Server Error';
  let details = null;

  // Handle specific error types
  if (error.name === 'ValidationError') {
    statusCode = 400;
    message = 'Validation Error';
    details = error.details;
  } else if (error.name === 'UnauthorizedError') {
    statusCode = 401;
    message = 'Unauthorized';
  } else if (error.name === 'ForbiddenError') {
    statusCode = 403;
    message = 'Forbidden';
  } else if (error.name === 'NotFoundError') {
    statusCode = 404;
    message = 'Not Found';
  } else if (error.name === 'ConflictError') {
    statusCode = 409;
    message = 'Conflict';
  } else if (error.name === 'RateLimitError') {
    statusCode = 429;
    message = 'Too Many Requests';
  }

  const errorResponse = {
    error: message,
    timestamp: new Date().toISOString(),
    path: req.path,
    method: req.method
  };

  // Include additional details in development
  if (isDevelopment) {
    errorResponse.details = details || error.message;
    errorResponse.stack = error.stack;
  }

  // Include trace ID if present
  if (req.headers['x-trace-id']) {
    errorResponse.traceId = req.headers['x-trace-id'];
  }

  res.status(statusCode).json(errorResponse);
};