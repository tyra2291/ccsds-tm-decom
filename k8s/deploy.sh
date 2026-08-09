#!/bin/bash
set -e

if [ ! -f .env ]; then
  echo "Missing .env file. Copy .env.example to .env and fill in real values first."
  exit 1
fi

echo "Generating PostgreSQL secret from .env (not committed to git)..."
kubectl create secret generic postgres-secret \
  --from-env-file=.env \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Applying PostgreSQL resources..."
kubectl apply -f k8s/postgres-schema-configmap.yaml
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml

echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres --timeout=90s

echo "Generating API config from .env (not committed to git)..."
source .env
kubectl create configmap api-config \
  --from-literal=DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Applying API resources..."
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml

echo "Waiting for API to be ready..."
kubectl wait --for=condition=ready pod -l app=api --timeout=90s

echo "Starting port-forward on http://localhost:8000 ..."
echo "Press Ctrl+C to stop."
kubectl port-forward service/api 8000:8000