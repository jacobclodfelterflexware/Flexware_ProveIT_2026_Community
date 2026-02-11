#!/bin/bash

# Test script for MQTT Topic Tree application
# This script verifies the deployment and runs basic tests

set -e

NAMESPACE="frontends"
APP_NAME="mqtt-topic-tree"
POD_SELECTOR="app=${APP_NAME}"

echo "=========================================="
echo "Testing MQTT Topic Tree Deployment"
echo "=========================================="
echo ""

# Check if namespace exists
echo "[1/7] Checking namespace..."
if kubectl get namespace ${NAMESPACE} &> /dev/null; then
    echo "✓ Namespace '${NAMESPACE}' exists"
else
    echo "✗ Namespace '${NAMESPACE}' does not exist"
    exit 1
fi

# Check if deployment exists
echo ""
echo "[2/7] Checking deployment..."
if kubectl get deployment ${APP_NAME} -n ${NAMESPACE} &> /dev/null; then
    echo "✓ Deployment '${APP_NAME}' exists"
else
    echo "✗ Deployment '${APP_NAME}' does not exist"
    exit 1
fi

# Check if pod is running
echo ""
echo "[3/7] Checking pod status..."
POD_STATUS=$(kubectl get pods -n ${NAMESPACE} -l ${POD_SELECTOR} -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")

if [ "$POD_STATUS" == "Running" ]; then
    echo "✓ Pod is running"
    POD_NAME=$(kubectl get pods -n ${NAMESPACE} -l ${POD_SELECTOR} -o jsonpath='{.items[0].metadata.name}')
    echo "  Pod name: ${POD_NAME}"
else
    echo "✗ Pod is not running (Status: ${POD_STATUS})"
    echo ""
    echo "Pod details:"
    kubectl get pods -n ${NAMESPACE} -l ${POD_SELECTOR}
    echo ""
    echo "Recent events:"
    kubectl get events -n ${NAMESPACE} --sort-by='.lastTimestamp' | tail -10
    exit 1
fi

# Check service
echo ""
echo "[4/7] Checking service..."
if kubectl get service ${APP_NAME} -n ${NAMESPACE} &> /dev/null; then
    echo "✓ Service '${APP_NAME}' exists"
    SERVICE_IP=$(kubectl get service ${APP_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.clusterIP}')
    echo "  Service IP: ${SERVICE_IP}"
else
    echo "✗ Service '${APP_NAME}' does not exist"
    exit 1
fi

# Test health endpoint
echo ""
echo "[5/7] Testing health endpoint..."
HEALTH_RESPONSE=$(kubectl exec -n ${NAMESPACE} ${POD_NAME} -- wget -q -O- http://localhost:YOUR_FRONTEND_PORT/health 2>/dev/null || echo "FAILED")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "✓ Health endpoint responding correctly"
    echo "  Response: ${HEALTH_RESPONSE}"
else
    echo "✗ Health endpoint not responding correctly"
    echo "  Response: ${HEALTH_RESPONSE}"
    exit 1
fi

# Check logs for errors
echo ""
echo "[6/7] Checking application logs..."
LOGS=$(kubectl logs -n ${NAMESPACE} ${POD_NAME} --tail=20 2>/dev/null || echo "FAILED")

if echo "$LOGS" | grep -qi "error"; then
    echo "⚠ Warning: Errors found in logs"
    echo "$LOGS" | grep -i "error" | tail -5
else
    echo "✓ No critical errors in recent logs"
fi

# Check MQTT connection
echo ""
echo "[7/7] Checking MQTT connection status..."
if echo "$LOGS" | grep -q "Successfully connected and subscribed"; then
    echo "✓ MQTT connection established"
elif echo "$LOGS" | grep -q "Attempting to reconnect"; then
    echo "⚠ MQTT connection issues (attempting to reconnect)"
else
    echo "ℹ MQTT connection status unknown (check logs for details)"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Namespace:   ${NAMESPACE}"
echo "Deployment:  ${APP_NAME}"
echo "Pod:         ${POD_NAME}"
echo "Status:      ${POD_STATUS}"
echo ""
echo "Access the dashboard:"
echo "  NodePort: http://<node-ip>:30800"
echo "  Port-forward: kubectl port-forward -n ${NAMESPACE} svc/${APP_NAME} 8080:YOUR_FRONTEND_PORT"
echo "  Then visit: http://localhost:YOUR_API_PORT"
echo ""
echo "View logs:"
echo "  kubectl logs -n ${NAMESPACE} -l ${POD_SELECTOR} -f"
echo ""
echo "✓ All tests passed!"
