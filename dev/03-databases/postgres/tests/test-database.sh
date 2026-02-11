#!/bin/bash

#
# PostgreSQL Database Deployment Test Script
# Tests deployment of PostgreSQL database in Kubernetes dev environment
#

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="postgres"
SERVICE_NAME="postgres-database"
DEPLOYMENT_NAME="postgres-database"
MANIFEST_DIR="/home/flexadmin/kubernetes/dev/03-databases/postgres"
TRAEFIK_IP="YOUR_LOADBALANCER_IP"  # Adjust to your Traefik LoadBalancer IP
POSTGRES_PORT=YOUR_POSTGRES_PORT
TIMEOUT=300

# Flags
CLEANUP=false

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --cleanup)
      CLEANUP=true
      shift
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --cleanup    Remove deployment after test"
      echo "  --timeout N  Wait timeout in seconds (default: 300)"
      echo "  --help       Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Cleanup function
cleanup() {
  if [ "$CLEANUP" = true ]; then
    echo -e "${YELLOW}Cleaning up PostgreSQL deployment...${NC}"
    kubectl delete -f "$MANIFEST_DIR/ingress.yaml" --ignore-not-found=true
    kubectl delete -f "$MANIFEST_DIR/service.yaml" --ignore-not-found=true
    kubectl delete -f "$MANIFEST_DIR/deployment.yaml" --ignore-not-found=true
    kubectl delete -f "$MANIFEST_DIR/pvc.yaml" --ignore-not-found=true
    kubectl delete -f "$MANIFEST_DIR/namespace.yaml" --ignore-not-found=true
    echo -e "${GREEN}Cleanup complete${NC}"
  fi
}

# Register cleanup on exit if requested
if [ "$CLEANUP" = true ]; then
  trap cleanup EXIT
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}PostgreSQL Database Deployment Test${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 1. Prerequisites check
echo -e "${YELLOW}[1/7] Checking prerequisites...${NC}"

if ! command -v kubectl &> /dev/null; then
  echo -e "${RED}ERROR: kubectl not found${NC}"
  exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
  echo -e "${RED}ERROR: Cannot connect to Kubernetes cluster${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# 2. Apply namespace
echo -e "${YELLOW}[2/7] Creating namespace...${NC}"
kubectl apply -f "$MANIFEST_DIR/namespace.yaml"
echo -e "${GREEN}✓ Namespace created${NC}"
echo ""

# 3. Apply PVC
echo -e "${YELLOW}[3/7] Creating PersistentVolumeClaim...${NC}"
kubectl apply -f "$MANIFEST_DIR/pvc.yaml"
echo -e "${GREEN}✓ PVC created${NC}"
echo ""

# 4. Apply deployment
echo -e "${YELLOW}[4/7] Creating deployment...${NC}"
kubectl apply -f "$MANIFEST_DIR/deployment.yaml"
echo -e "${GREEN}✓ Deployment created${NC}"
echo ""

# 5. Apply service
echo -e "${YELLOW}[5/7] Creating service...${NC}"
kubectl apply -f "$MANIFEST_DIR/service.yaml"
echo -e "${GREEN}✓ Service created${NC}"
echo ""

# 6. Apply ingress
echo -e "${YELLOW}[6/7] Creating Traefik IngressRouteTCP...${NC}"
kubectl apply -f "$MANIFEST_DIR/ingress.yaml"
echo -e "${GREEN}✓ IngressRouteTCP created${NC}"
echo ""

# 7. Wait for deployment to be ready
echo -e "${YELLOW}[7/7] Waiting for deployment to be ready (timeout: ${TIMEOUT}s)...${NC}"

# Wait for deployment
if kubectl wait --for=condition=available --timeout="${TIMEOUT}s" \
  deployment/$DEPLOYMENT_NAME -n $NAMESPACE 2>/dev/null; then
  echo -e "${GREEN}✓ Deployment is ready${NC}"
else
  echo -e "${RED}ERROR: Deployment failed to become ready${NC}"
  echo ""
  echo "Deployment status:"
  kubectl get deployment $DEPLOYMENT_NAME -n $NAMESPACE
  echo ""
  echo "Pod status:"
  kubectl get pods -n $NAMESPACE
  echo ""
  echo "Pod logs:"
  kubectl logs -n $NAMESPACE -l app=postgres --tail=50
  exit 1
fi

echo ""

# Test database connectivity
echo -e "${YELLOW}Testing database connectivity...${NC}"

# Get pod name
POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=postgres -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
  echo -e "${RED}ERROR: Could not find PostgreSQL pod${NC}"
  exit 1
fi

echo "Pod name: $POD_NAME"

# Test database connection using pg_isready
echo -e "${YELLOW}Running pg_isready check...${NC}"
if kubectl exec -n $NAMESPACE $POD_NAME -- pg_isready -U postgres; then
  echo -e "${GREEN}✓ Database is accepting connections${NC}"
else
  echo -e "${RED}ERROR: Database is not ready${NC}"
  exit 1
fi

# Test database query
echo -e "${YELLOW}Testing database query...${NC}"
if kubectl exec -n $NAMESPACE $POD_NAME -- psql -U postgres -c "SELECT version();" > /dev/null 2>&1; then
  echo -e "${GREEN}✓ Database query successful${NC}"

  # Show PostgreSQL version
  echo ""
  echo "PostgreSQL version:"
  kubectl exec -n $NAMESPACE $POD_NAME -- psql -U postgres -t -c "SELECT version();"
else
  echo -e "${RED}ERROR: Database query failed${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Test: PASSED${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Deployment details:"
echo "  Namespace:  $NAMESPACE"
echo "  Service:    $SERVICE_NAME"
echo "  Deployment: $DEPLOYMENT_NAME"
echo ""
echo "Connection information:"
echo "  Internal (within cluster):"
echo "    Host: $SERVICE_NAME.$NAMESPACE.svc.cluster.local"
echo "    Port: 5432"
echo "    User: postgres"
echo "    Password: password"
echo ""
echo "  External (via Traefik - requires 'postgres' entry point):"
echo "    Host: $TRAEFIK_IP"
echo "    Port: [configured in Traefik for 'postgres' entry point]"
echo "    User: postgres"
echo "    Password: password"
echo ""
echo "Example connection string (internal):"
echo "  postgresql://YOUR_DB_USERNAME:YOUR_DB_PASSWORD@$SERVICE_NAME.$NAMESPACE.svc.cluster.local:YOUR_POSTGRES_PORT/postgres"
echo ""
echo "Verify deployment:"
echo "  kubectl get all -n $NAMESPACE"
echo ""
echo "Access PostgreSQL shell:"
echo "  kubectl exec -it -n $NAMESPACE $POD_NAME -- psql -U postgres"
echo ""
echo "View logs:"
echo "  kubectl logs -n $NAMESPACE -l app=postgres"
echo ""

if [ "$CLEANUP" = false ]; then
  echo -e "${YELLOW}Note: Use --cleanup flag to automatically remove deployment after test${NC}"
  echo ""
fi
