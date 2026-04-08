# Intangible-Asset Risk Guardian (IARG)

An agentic solution that provides asset discovery, risk scoring, and coverage optimization for intangible assets.

## Architecture Overview

IARG is an event-driven, microservices-based system that:
- Discovers intangible assets across repositories (GitHub, Snowflake, Google Drive)
- Scores risk dynamically using AI models
- Values assets using international standards
- Optimizes insurance coverage automatically

## Project Structure

```
./app
├── edge/          # Cloudflare Worker for webhook ingestion
├── ingest/        # Event normalization and routing
├── graph/         # Go service for Neo4j asset graph
├── score/         # Python AI risk scorer (XGBoost, TF Serving)
├── insure/        # Go insurance engine with Stripe integration
├── dash/          # React + Vite frontend dashboard
├── iac/           # Terraform IaC for Azure deployment
├── tools/         # Dev utilities, scripts, and CI/CD helpers
├── docs/          # Documentation and architecture diagrams
└── scripts/       # Local setup, health checks, and automation
```

## Technology Stack

- **Backend**: Go, Python, Node.js
- **Frontend**: React + Vite + Tailwind CSS
- **Databases**: Neo4j Aura, Redis
- **Event Streaming**: Azure Event Hub, Kafka
- **AI/ML**: XGBoost, TensorFlow Serving
- **Cloud**: Azure (Container Instances, Key Vault, Blob Storage)
- **Infrastructure**: Terraform
- **Edge**: Cloudflare Workers

## Quick Start

1. **Prerequisites**
   ```bash
   # Install required tools
   node --version  # >= 18
   go version      # >= 1.21
   python --version # >= 3.9
   docker --version
   terraform --version
   ```

2. **Local Development Setup**
   ```bash
   # Clone and setup
   git clone <repository>
   cd iarg
   
   # Install dependencies
   npm install
   
   # Start local services
   docker-compose up -d
   
   # Run development servers
   npm run dev
   ```

3. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

## Development Phases

- [x] **Phase 1**: Research & Foundations
- [x] **Phase 2**: Technical Architecture & Stack Setup
- [x] **Phase 3**: Data & Event Infrastructure (In Progress)
- [x] **Phase 4**: Core Service Development
- [x] **Phase 5**: Integration & Validation
- [x] **Phase 6**: Evaluation & Optimization
