#!/usr/bin/env bash
# ==============================================================================
# Deploy/Update Telegram Bots Platform on k3s Kubernetes
# ==============================================================================
set -euo pipefail

REPO_DIR="/opt/telegram-bots"
cd "${REPO_DIR}"

TARGET="${1:-all}"
echo "🚀 Deploying Telegram Bots Platform to k3s (target: ${TARGET})..."

# Pull latest changes if run directly on server
if [ -d .git ]; then
    echo "📥 Pulling latest git changes..."
    git pull origin main || true
fi

# Build Docker image
echo "🐳 Building Docker image..."
docker build -t telegram-bots-platform:latest .

# Ensure namespace exists
k3s kubectl get ns telegram-bots >/dev/null 2>&1 || k3s kubectl create ns telegram-bots

# Sync Secrets from .env if present
if [ -f .env ]; then
    echo "🔐 Syncing Kubernetes secret..."
    k3s kubectl delete secret telegram-bots-secret -n telegram-bots --ignore-not-found=true
    k3s kubectl create secret generic telegram-bots-secret \
        --namespace telegram-bots \
        --from-env-file=.env
fi

# Apply Kustomize manifests
echo "📦 Applying k8s manifests..."
k3s kubectl apply -k k8s/

# Rollout restart based on target
if [ "${TARGET}" = "all" ]; then
    echo "🔄 Rolling restart all bot deployments..."
    k3s kubectl rollout restart deployment -n telegram-bots
elif [ "${TARGET}" = "webhook_server" ]; then
    k3s kubectl rollout restart deployment/webhook-server -n telegram-bots
elif [ "${TARGET}" = "ai_worker" ]; then
    k3s kubectl rollout restart deployment/ai-worker -n telegram-bots
elif [ "${TARGET}" = "image_bot_1" ]; then
    k3s kubectl rollout restart deployment/image-bot-1 -n telegram-bots
elif [ "${TARGET}" = "admin_bot" ]; then
    k3s kubectl rollout restart deployment/admin-bot -n telegram-bots
elif [ "${TARGET}" = "redis" ]; then
    k3s kubectl rollout restart deployment/redis -n telegram-bots
fi

# Check rollout status
echo "⏳ Checking rollout status..."
k3s kubectl rollout status deployment/webhook-server -n telegram-bots --timeout=60s || true

echo "📊 Current Pod Status:"
k3s kubectl get pods -n telegram-bots -o wide
