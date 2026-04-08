// Health check script for Docker healthcheck
import http from 'http';

const options = {
  hostname: 'localhost',
  port: process.env.PORT || 3001,
  // Express route is mounted at `/health` with a `/` handler => `/health/`.
  // Some setups treat `/health` vs `/health/` differently for healthchecks.
  path: '/health/',
  method: 'GET',
  timeout: 3000
};

const req = http.request(options, (res) => {
  if (res.statusCode === 200) {
    process.exit(0);
  } else {
    process.exit(1);
  }
});

req.on('error', () => {
  process.exit(1);
});

req.on('timeout', () => {
  req.destroy();
  process.exit(1);
});

req.end();