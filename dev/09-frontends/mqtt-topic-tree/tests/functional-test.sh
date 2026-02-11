#!/bin/bash

# Functional test for MQTT Topic Tree Dashboard
# Tests the deployed application via HTTP requests

set -e

BASE_URL="${BASE_URL:-http://localhost:8080}"
PASS_COUNT=0
FAIL_COUNT=0

echo "=========================================="
echo "MQTT Topic Tree - Functional Tests"
echo "=========================================="
echo "Testing against: $BASE_URL"
echo ""

# Test function
test_endpoint() {
    local name="$1"
    local endpoint="$2"
    local expected="$3"

    echo -n "Testing: $name... "

    response=$(curl -s "$BASE_URL$endpoint" || echo "CURL_FAILED")

    if echo "$response" | grep -q "$expected"; then
        echo "✓ PASS"
        ((PASS_COUNT++))
        return 0
    else
        echo "✗ FAIL"
        echo "  Expected to find: $expected"
        echo "  Got: ${response:0:200}"
        ((FAIL_COUNT++))
        return 1
    fi
}

# Test 1: Health endpoint
test_endpoint "Health Endpoint" "/health" "healthy"

# Test 2: Main page loads
test_endpoint "Dashboard Page Load" "/" "MQTT Topic Explorer"

# Test 3: Check for React root
test_endpoint "React Application" "/" "<div id="

# Test 4: Check for connection status element
test_endpoint "Connection Status UI" "/" "Connected"

# Test 5: Check for topic tree panel
test_endpoint "Topic Tree Panel" "/" "Topic Tree"

# Test 6: Check for topic details panel
test_endpoint "Topic Details Panel" "/" "Topic Details"

# Test 7: Check for broker selector
test_endpoint "Broker Selector" "/" "Uncurated"

# Test 8: MQTT API endpoint accessibility
echo -n "Testing: MQTT API Endpoint (SSE)... "
if curl -s -N "$BASE_URL/api/mqtt?broker=uncurated" --max-time 5 | head -1 | grep -q "event:"; then
    echo "✓ PASS"
    ((PASS_COUNT++))
else
    echo "✗ FAIL"
    ((FAIL_COUNT++))
fi

# Test 9: Check NodePort accessibility (if BASE_URL uses nodeport)
if [ "$BASE_URL" != "http://localhost:YOUR_API_PORT" ]; then
    test_endpoint "NodePort Access" "/" "MQTT Topic Explorer"
fi

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"
echo "Total:  $((PASS_COUNT + FAIL_COUNT))"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi
