#!/bin/bash

# IARG Setup Script
# This script sets up the development environment for the IARG project

set -e

echo "🚀 Setting up IARG Development Environment"

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js >= 18"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version must be >= 18. Current version: $(node --version)"
    exit 1
fi

# Check Go
if ! command -v go &> /dev/null; then
    echo "❌ Go is not installed. Please install Go >= 1.21"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python >= 3.9"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose"
    exit 1
fi

echo "✅ All prerequisites are installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. Please update it with your configuration."
fi

# Install root dependencies
echo "📦 Installing root dependencies..."
npm install

# Setup services
echo "🔧 Setting up services..."

# Setup ingest service
echo "  📦 Setting up ingest service..."
cd app/ingest
npm install
cd ../..

# Setup dashboard
echo "  📦 Setting up dashboard..."
cd app/dash
npm install
cd ../..

# Setup Go services
echo "  📦 Setting up Go services..."
cd app/graph
go mod tidy
cd ../..

# Setup Python services
echo "  📦 Setting up Python services..."
cd app/score
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ../..

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data
mkdir -p models

# Start infrastructure services
echo "🐳 Starting infrastructure services..."
docker-compose up -d kafka neo4j redis ipfs minio

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🏥 Checking service health..."

# Check Kafka
if docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list &> /dev/null; then
    echo "✅ Kafka is ready"
else
    echo "⚠️  Kafka might not be ready yet"
fi

# Check Neo4j
if docker-compose exec neo4j cypher-shell -u neo4j -p password123 "RETURN 1" &> /dev/null; then
    echo "✅ Neo4j is ready"
else
    echo "⚠️  Neo4j might not be ready yet"
fi

# Check Redis
if docker-compose exec redis redis-cli -a redis123 ping &> /dev/null; then
    echo "✅ Redis is ready"
else
    echo "⚠️  Redis might not be ready yet"
fi

echo ""
echo "🎉 IARG Development Environment Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Update your .env file with the necessary API keys and configuration"
echo "2. Run 'npm run dev' to start the development servers"
echo "3. Visit http://localhost:3000 to access the dashboard"
echo ""
echo "Useful commands:"
echo "  npm run dev          - Start all development servers"
echo "  npm run docker:up    - Start infrastructure services"
echo "  npm run docker:down  - Stop infrastructure services"
echo "  npm run docker:logs  - View infrastructure logs"
echo "  npm test             - Run all tests"
echo ""