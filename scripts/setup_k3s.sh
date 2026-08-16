#!/usr/bin/env bash
# ==============================================================================
# Setup k3s Lightweight Kubernetes on Single-Node Hetzner Server
# ==============================================================================
set -euo pipefail

echo "======================================================================"
echo "🚀 Starting k3s Kubernetes Setup for Telegram Bots Platform"
echo "======================================================================"

REPO_DIR="/opt/telegram-bots"
cd "${REPO_DIR}"

# 1. Setup 2GB Swap if not already configured
if [ ! -f /swapfile ]; then
    echo "⚙️ Creating 2GB swapfile for memory stability..."
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    echo "✅ Swapfile created and enabled."
else
    echo "ℹ️ Swapfile already exists."
fi

# 2. Install k3s with Docker support
if ! command -v k3s &> /dev/null; then
    echo "📦 Installing k3s (with --docker integration)..."
    curl -sfL https://get.k3s.io | sh -s - --docker --write-kubeconfig-mode 644
    echo "✅ k3s installed successfully."
else
    echo "ℹ️ k3s is already installed."
fi

# Wait for k3s service to be active and ready
echo "⏳ Waiting for k3s cluster to be ready..."
sleep 5
k3s kubectl wait --for=condition=Ready node --all --timeout=60s || true
k3s kubectl get nodes -o wide

# 3. Stop legacy Docker Compose containers to free up host ports (8000, 6379)
echo "🛑 Stopping legacy Docker Compose containers..."
docker compose down || true

# 4. Build latest Docker image locally
echo "🐳 Building Docker image for Telegram Bots Platform..."
docker build -t telegram-bots-platform:latest .

# 5. Ensure namespace and create/update Kubernetes secret from .env
echo "🔐 Setting up namespace and secrets..."
k3s kubectl get ns telegram-bots >/dev/null 2>&1 || k3s kubectl create ns telegram-bots

if [ -f .env ]; then
    echo "🔐 Syncing Kubernetes secret from .env..."
    k3s kubectl delete secret telegram-bots-secret -n telegram-bots --ignore-not-found=true
    k3s kubectl create secret generic telegram-bots-secret \
        --namespace telegram-bots \
        --from-env-file=.env
    echo "✅ Secret telegram-bots-secret updated."
else
    echo "⚠️ Warning: .env file not found in ${REPO_DIR}!"
fi

# 6. Apply all Kubernetes manifests via Kustomize
echo "🚀 Applying Kubernetes manifests in k8s/..."
k3s kubectl apply -k k8s/

# 7. Wait for rollout status of all deployments
echo "⏳ Waiting for deployments to roll out..."
k3s kubectl rollout status deployment/redis -n telegram-bots --timeout=90s
k3s kubectl rollout status deployment/webhook-server -n telegram-bots --timeout=90s
k3s kubectl rollout status deployment/ai-worker -n telegram-bots --timeout=90s
k3s kubectl rollout status deployment/image-bot-1 -n telegram-bots --timeout=90s
k3s kubectl rollout status deployment/admin-bot -n telegram-bots --timeout=90s

echo "======================================================================"
echo "🎉 k3s Kubernetes Deployment Complete!"
echo "======================================================================"
k3s kubectl get all -n telegram-bots
