#!/usr/bin/env bash
# One-click cloud build and deployment script for SupplyChain Autopilot
set -e

echo "=== SupplyChain Autopilot Cloud Deployment Helper ==="
echo "Targeting container images: backend, crewai-service, frontend"

# Check if docker is installed
if command -v docker &> /dev/null; then
    echo "1. Building Docker container images locally..."
    docker compose build
    echo "✓ Local Docker images built successfully."
else
    echo "⚠️ Docker daemon not found in PATH. Skipping local image build."
fi

echo "2. Ready for Cloud Platform Deployments:"
echo " - Render: Import repository and select 'deploy/render.yaml' for automated multi-service deploy."
echo " - Fly.io: Run 'fly launch --config deploy/fly.toml'."
echo " - Google Cloud Run: 'gcloud run deploy --source .'"
echo " - AWS App Runner / ECS: Push images to ECR and deploy docker-compose.yml."
echo "=== Deployment preparations complete. ==="
