#!/bin/bash

# EMQX Curated Broker Deployment Test Script
# This script tests the deployment of the EMQX Curated broker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="emqx-curated"
DEPLOYMENT_NAME="emqx-broker"
SERVICE_NAME="emqx-broker"
MANIFEST_DIR="../"
TRAEFIK_IP="YOUR_REGISTRY_IP"

echo "======================================"
echo "EMQX Curated Broker Deployment Test"
echo "======================================"
echo ""

# Function to print colored output
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        exit 1
    fi
}

# Check prerequisites
echo "Checking prerequisites..."

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    print_status 1 "kubectl not found. Please install kubectl."
fi
print_status 0 "kubectl is installed"

# Check cluster connection
if ! kubectl cluster-info &> /dev/null; then
    print_status 1 "Cannot connect to Kubernetes cluster"
fi
print_status 0 "Connected to Kubernetes cluster"

# Check if Traefik is running
if ! kubectl get deployment traefik -n kube-system &> /dev/null; then
    print_status 1 "Traefik not found in kube-system namespace"
fi
print_status 0 "Traefik is running"

echo ""
echo "Deploying EMQX Curated Broker..."
echo ""

# Apply manifests in order
echo "Creating namespace..."
kubectl apply -f "${MANIFEST_DIR}/namespace.yaml"
print_status $? "Namespace created"

echo "Creating PVC..."
kubectl apply -f "${MANIFEST_DIR}/pvc.yaml"
print_status $? "PVC created"

echo "Creating deployment..."
kubectl apply -f "${MANIFEST_DIR}/deployment.yaml"
print_status $? "Deployment created"

echo "Creating service..."
kubectl apply -f "${MANIFEST_DIR}/service.yaml"
print_status $? "Service created"

echo "Creating ingress..."
kubectl apply -f "${MANIFEST_DIR}/ingress.yaml"
print_status $? "Ingress created"

echo ""
echo "Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}
print_status $? "Deployment is ready"

echo ""
echo "Checking pod status..."
kubectl get pods -n ${NAMESPACE}

echo ""
echo "Testing EMQX Dashboard endpoint..."
sleep 5

# Test dashboard access via Traefik
if curl -s -o /dev/null -w "%{http_code}" "http://${TRAEFIK_IP}:YOUR_EMQX_DASHBOARD_PORT" | grep -q "200\|301\|302"; then
    print_status 0 "Dashboard is accessible via Traefik (port 18083)"
else
    echo -e "${YELLOW}⚠ Dashboard may not be fully ready yet. Check manually.${NC}"
fi

echo ""
echo "======================================"
echo "Deployment Information"
echo "======================================"
echo ""
echo "Namespace: ${NAMESPACE}"
echo "Deployment: ${DEPLOYMENT_NAME}"
echo "Service: ${SERVICE_NAME}"
echo ""
echo "Access URLs (via Traefik LoadBalancer):"
echo "  Dashboard:        http://${TRAEFIK_IP}:YOUR_EMQX_DASHBOARD_PORT"
echo "  MQTT:             mqtt://${TRAEFIK_IP}:YOUR_MQTT_PORT"
echo "  MQTT/TLS:         mqtts://${TRAEFIK_IP}:YOUR_MQTT_SSL_PORT"
echo "  MQTT/WebSocket:   ws://${TRAEFIK_IP}:YOUR_MQTT_WS_PORT"
echo "  MQTT/WSS:         wss://${TRAEFIK_IP}:YOUR_MQTT_WSS_PORT"
echo ""
echo "Default Credentials:"
echo "  Username: admin"
echo "  Password: "YOUR_MQTT_PASSWORD"
echo ""
echo "======================================"
echo "Useful Commands"
echo "======================================"
echo ""
echo "View logs:"
echo "  kubectl logs -f deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}"
echo ""
echo "View service details:"
echo "  kubectl get svc ${SERVICE_NAME} -n ${NAMESPACE}"
echo ""
echo "View ingress routes:"
echo "  kubectl get ingressroute,ingressroutetcp -n ${NAMESPACE}"
echo ""
echo "Delete deployment:"
echo "  kubectl delete -f ${MANIFEST_DIR}"
echo ""
