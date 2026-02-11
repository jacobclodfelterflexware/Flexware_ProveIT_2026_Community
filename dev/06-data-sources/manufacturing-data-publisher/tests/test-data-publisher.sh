#!/bin/bash
#
# Test script for manufacturing-data-publisher deployment
# This script deploys the application and verifies it's running correctly
#

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="data-sources"
DEPLOYMENT_NAME="manufacturing-data-publisher"
SERVICE_NAME="manufacturing-data-publisher"
MANIFEST_DIR="$(dirname "$0")/.."
IMAGE_NAME="manufacturing-data-publisher:latest"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}Manufacturing Data Publisher - Deployment Test${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Function to print colored status messages
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found. Please install kubectl."
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to Kubernetes cluster."
    exit 1
fi

print_success "Prerequisites check passed"
echo ""

# Build Docker image
print_status "Building Docker image..."
cd "${MANIFEST_DIR}"

if docker build -t "${IMAGE_NAME}" . ; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi
echo ""

# Apply Kubernetes manifests
print_status "Applying Kubernetes manifests..."

print_status "Creating namespace..."
kubectl apply -f "${MANIFEST_DIR}/namespace.yaml"

print_status "Creating deployment..."
kubectl apply -f "${MANIFEST_DIR}/deployment.yaml"

print_status "Creating service..."
kubectl apply -f "${MANIFEST_DIR}/service.yaml"

print_status "Creating ingress..."
kubectl apply -f "${MANIFEST_DIR}/ingress.yaml"

print_success "All manifests applied"
echo ""

# Wait for deployment to be ready
print_status "Waiting for deployment to be ready (timeout: 300s)..."
if kubectl wait --for=condition=available --timeout=300s deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}; then
    print_success "Deployment is ready"
else
    print_error "Deployment failed to become ready"
    echo ""
    print_status "Pod status:"
    kubectl get pods -n ${NAMESPACE} -l app=${DEPLOYMENT_NAME}
    echo ""
    print_status "Pod logs:"
    kubectl logs -n ${NAMESPACE} -l app=${DEPLOYMENT_NAME} --tail=50
    exit 1
fi
echo ""

# Get pod information
print_status "Deployment status:"
kubectl get deployment -n ${NAMESPACE} ${DEPLOYMENT_NAME}
echo ""

print_status "Pod status:"
kubectl get pods -n ${NAMESPACE} -l app=${DEPLOYMENT_NAME}
echo ""

print_status "Service status:"
kubectl get service -n ${NAMESPACE} ${SERVICE_NAME}
echo ""

# Test health endpoint
print_status "Testing health endpoint..."
POD_NAME=$(kubectl get pods -n ${NAMESPACE} -l app=${DEPLOYMENT_NAME} -o jsonpath='{.items[0].metadata.name}')

if kubectl exec -n ${NAMESPACE} ${POD_NAME} -- curl -s http://localhost:YOUR_API_PORT_2/health > /dev/null; then
    print_success "Health endpoint is responding"

    # Show health data
    echo ""
    print_status "Health check response:"
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- curl -s http://localhost:YOUR_API_PORT_2/health | python3 -m json.tool || true
else
    print_warning "Health endpoint is not responding"
fi
echo ""

# Show application logs
print_status "Recent application logs:"
echo -e "${BLUE}------------------------------------------------------------${NC}"
kubectl logs -n ${NAMESPACE} ${POD_NAME} --tail=30
echo -e "${BLUE}------------------------------------------------------------${NC}"
echo ""

# Test MQTT connectivity by checking logs
print_status "Checking MQTT connectivity..."
if kubectl logs -n ${NAMESPACE} ${POD_NAME} | grep -q "Connected to MQTT broker"; then
    print_success "MQTT connections established"
else
    print_warning "MQTT connection messages not found in logs"
fi
echo ""

# Show data publishing stats
print_status "Checking data publishing..."
if kubectl logs -n ${NAMESPACE} ${POD_NAME} | grep -q "Starting publisher"; then
    print_success "Data publishers are running"

    # Count publisher threads
    MACHINE_COUNT=$(kubectl logs -n ${NAMESPACE} ${POD_NAME} | grep -c "Machine-" || echo "0")
    SYSTEM_COUNT=$(kubectl logs -n ${NAMESPACE} ${POD_NAME} | grep -c "System-" || echo "0")

    echo ""
    print_status "Publisher statistics:"
    echo "  Machine publishers: ${MACHINE_COUNT}"
    echo "  Enterprise system publishers: ${SYSTEM_COUNT}"
else
    print_warning "Data publisher status unclear"
fi
echo ""

# Summary and access information
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}Deployment Summary${NC}"
echo -e "${BLUE}============================================================${NC}"
print_success "Manufacturing Data Publisher is deployed and running"
echo ""
echo "Namespace: ${NAMESPACE}"
echo "Deployment: ${DEPLOYMENT_NAME}"
echo "Pod: ${POD_NAME}"
echo ""
echo -e "${BLUE}Health Check:${NC}"
echo "  Internal: http://${SERVICE_NAME}.${NAMESPACE}.svc.cluster.local:YOUR_API_PORT_2/health"
echo "  Port Forward: kubectl port-forward -n ${NAMESPACE} svc/${SERVICE_NAME} 8090:YOUR_API_PORT_2"
echo ""
echo -e "${BLUE}MQTT Brokers:${NC}"
echo "  Curated: YOUR_MQTT_CURATED_HOST:YOUR_MQTT_PORT"
echo "  Uncurated: YOUR_MQTT_UNCURATED_HOST:YOUR_MQTT_PORT"
echo ""
echo -e "${BLUE}Data being published:${NC}"
echo "  - 100 Machine assets (CNC, Robots, Conveyors, etc.)"
echo "  - 50 Enterprise systems (ERP, MES, SCADA, DCS, WMS, AGV)"
echo "  - Mix of UNS and flat topic structures"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  View logs: kubectl logs -n ${NAMESPACE} -f ${POD_NAME}"
echo "  View health: kubectl exec -n ${NAMESPACE} ${POD_NAME} -- curl http://localhost:YOUR_API_PORT_2/health"
echo "  Delete deployment: kubectl delete -f ${MANIFEST_DIR}/deployment.yaml"
echo "  Delete all resources: kubectl delete namespace ${NAMESPACE}"
echo ""
echo -e "${BLUE}To subscribe to MQTT topics:${NC}"
echo "  # From inside cluster:"
echo "  kubectl run -n emqx-curated -it --rm mqtt-client --image=eclipse-mosquitto:latest --restart=Never -- \\"
echo "    mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD -t '#' -v"
echo ""
echo -e "${BLUE}To update Traefik for external access on port 8090:${NC}"
echo "  kubectl edit svc traefik -n kube-system"
echo "  # Add this port entry:"
echo "  #   - name: datasources"
echo "  #     port: YOUR_API_PORT_2"
echo "  #     protocol: TCP"
echo "  #     targetPort: datasources"
echo ""
echo -e "${GREEN}Deployment test completed successfully!${NC}"
echo -e "${BLUE}============================================================${NC}"
