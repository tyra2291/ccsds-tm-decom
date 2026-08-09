#!/bin/bash
set -e

echo "Applying PostgreSQL resources..."
kubectl apply -f k8s/postgres-secret.yaml
kubectl apply -f k8s/postgres-schema-configmap.yaml
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml

echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres --timeout=90s

echo "Applying API resources..."
kubectl apply -f k8s/api-configmap.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml

echo "Waiting for API to be ready..."
kubectl wait --for=condition=ready pod -l app=api --timeout=90s

echo "Done. Access the UI with:"
echo "  kubectl port-forward service/api 8000:8000"
echo "Then open http://localhost:8000"