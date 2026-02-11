# Quick Deployment Guide

## Prerequisites Check

Before deploying, ensure:

1. **EMQX Brokers are running**:
```bash
kubectl get pods -n emqx-curated
kubectl get pods -n emqx-uncurated
```

2. **Traefik is running**:
```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik
```

3. **Docker is available**:
```bash
docker version
```

## Quick Deploy (Using Test Script)

The fastest way to deploy is using the included test script:

```bash
cd /home/flexadmin/kubernetes/dev/06-data-sources/manufacturing-data-publisher
./tests/test-data-publisher.sh
```

This will:
- Build the Docker image
- Apply all manifests
- Wait for deployment
- Run health checks
- Display access information

## Manual Deployment Steps

### 1. Build Docker Image

```bash
cd /home/flexadmin/kubernetes/dev/06-data-sources/manufacturing-data-publisher
docker build -t manufacturing-data-publisher:latest .
```

### 2. Apply Kubernetes Manifests

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Deploy application
kubectl apply -f deployment.yaml

# Create service
kubectl apply -f service.yaml

# Create ingress route
kubectl apply -f ingress.yaml
```

### 3. Verify Deployment

```bash
# Check deployment status
kubectl get deployment -n data-sources

# Check pods
kubectl get pods -n data-sources

# Wait for pod to be ready
kubectl wait --for=condition=ready --timeout=300s pod -n data-sources -l app=manufacturing-data-publisher
```

### 4. Check Application Logs

```bash
# Follow logs
kubectl logs -n data-sources -l app=manufacturing-data-publisher -f

# Look for these key messages:
# - "Connected to MQTT broker" (should see 2 - curated and uncurated)
# - "Created X machines"
# - "Created X enterprise systems"
# - "Starting publisher for..."
# - "Application started successfully"
```

### 5. Test Health Endpoint

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n data-sources -l app=manufacturing-data-publisher -o jsonpath='{.items[0].metadata.name}')

# Test health endpoint
kubectl exec -n data-sources ${POD_NAME} -- curl -s http://localhost:YOUR_API_PORT_2/health | python3 -m json.tool
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": 1234567890123,
  "machine_stats": {
    "total_machines": 100,
    "active_threads": 100,
    ...
  },
  "enterprise_stats": {
    "total_systems": 50,
    "active_threads": 50,
    ...
  }
}
```

## Verify Data Publishing

### Subscribe to MQTT Topics

Test that data is being published to the MQTT brokers:

```bash
# Subscribe to all machine telemetry on curated broker
kubectl run -n emqx-curated -it --rm mqtt-test --image=eclipse-mosquitto:latest --restart=Never -- \
  mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD \
  -t 'acme-manufacturing/plant-01/#' -C 10 -v

# Subscribe to all topics on uncurated broker
kubectl run -n emqx-uncurated -it --rm mqtt-test --image=eclipse-mosquitto:latest --restart=Never -- \
  mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD \
  -t '#' -C 20 -v
```

You should see JSON messages with machine telemetry and enterprise system data.

## Enable External Access (Optional)

To access the health endpoint from outside the cluster:

### Option 1: Port Forward (Temporary)

```bash
kubectl port-forward -n data-sources svc/manufacturing-data-publisher 8090:YOUR_API_PORT_2
```

Then access: `http://localhost:YOUR_API_PORT_2/health`

### Option 2: Add Traefik Entrypoint (Permanent)

1. **Edit Traefik Service** to add port 8090:

```bash
kubectl edit svc traefik -n kube-system
```

Add this port entry under `spec.ports`:
```yaml
- name: datasources
  port: YOUR_API_PORT_2
  protocol: TCP
  targetPort: datasources
```

2. **Edit Traefik Deployment** to add entrypoint:

```bash
kubectl edit deployment traefik -n kube-system
```

Add this argument under `spec.template.spec.containers[0].args`:
```yaml
- --entrypoints.datasources.address=:YOUR_API_PORT_2
```

3. **Wait for Traefik to restart**:

```bash
kubectl rollout status deployment traefik -n kube-system
```

4. **Access via LoadBalancer**:

```bash
curl http://YOUR_REGISTRY_IP:YOUR_API_PORT_2/health
```

## Configuration Adjustments

### Change Number of Assets

Edit [deployment.yaml](deployment.yaml) and modify these environment variables:

```yaml
- name: NUM_MACHINES
  value: "100"  # Change this
- name: NUM_ENTERPRISE_SYSTEMS
  value: "50"   # Change this
```

Then restart:
```bash
kubectl rollout restart deployment/manufacturing-data-publisher -n data-sources
```

### Change Publishing Intervals

Modify these environment variables in [deployment.yaml](deployment.yaml):

```yaml
- name: MACHINE_PUBLISH_INTERVAL_MIN
  value: "1.0"   # Faster = more messages
- name: MACHINE_PUBLISH_INTERVAL_MAX
  value: "10.0"  # Slower = fewer messages
```

### Change UNS Hierarchy

Modify these to match your organization:

```yaml
- name: ENTERPRISE
  value: "acme-manufacturing"  # Your company name
- name: SITE
  value: "plant-01"            # Your site name
```

## Monitoring

### Watch Pod Resource Usage

```bash
kubectl top pod -n data-sources
```

### View Events

```bash
kubectl get events -n data-sources --sort-by='.lastTimestamp'
```

### Check Health Over Time

```bash
# Create a monitoring loop
POD_NAME=$(kubectl get pods -n data-sources -l app=manufacturing-data-publisher -o jsonpath='{.items[0].metadata.name}')

while true; do
  echo "=== $(date) ==="
  kubectl exec -n data-sources ${POD_NAME} -- curl -s http://localhost:YOUR_API_PORT_2/health | \
    python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"Machines: {data['machine_stats']['active_threads']}/{data['machine_stats']['total_machines']}, Systems: {data['enterprise_stats']['active_threads']}/{data['enterprise_stats']['total_systems']}\")"
  sleep 30
done
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod -n data-sources -l app=manufacturing-data-publisher

# Check deployment events
kubectl describe deployment -n data-sources manufacturing-data-publisher
```

### MQTT Connection Issues

```bash
# Check MQTT broker connectivity
kubectl run -n data-sources -it --rm mqtt-test --image=eclipse-mosquitto:latest --restart=Never -- \
  mosquitto_pub -h YOUR_MQTT_CURATED_HOST -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD -t test -m "hello"

# Check if brokers are running
kubectl get pods -n emqx-curated
kubectl get pods -n emqx-uncurated
```

### Image Pull Issues

```bash
# If using a custom registry, ensure imagePullSecrets are configured
# For local images, ensure imagePullPolicy is set to IfNotPresent or Never

# Check current image policy
kubectl get deployment -n data-sources manufacturing-data-publisher -o jsonpath='{.spec.template.spec.containers[0].imagePullPolicy}'
```

### High Memory Usage

If the pod uses more than 1Gi memory, adjust the limits:

```bash
kubectl edit deployment -n data-sources manufacturing-data-publisher
```

Modify:
```yaml
resources:
  limits:
    memory: "2Gi"  # Increase if needed
```

## Cleanup

### Delete Application Only

```bash
kubectl delete deployment -n data-sources manufacturing-data-publisher
kubectl delete service -n data-sources manufacturing-data-publisher
kubectl delete ingressroute -n data-sources data-publisher-health
```

### Delete Everything (Including Namespace)

```bash
kubectl delete namespace data-sources
```

## Next Steps

After deployment:

1. **Monitor MQTT brokers** - Check message rates in EMQX dashboards
2. **Set up data consumers** - Create applications that subscribe to the topics
3. **Configure data persistence** - Set up InfluxDB, TimescaleDB, or other time-series databases
4. **Build dashboards** - Use Grafana to visualize the data
5. **Implement data processing** - Add Spark Streaming or similar for analytics

## Support

For issues, check:
- Application logs: `kubectl logs -n data-sources -l app=manufacturing-data-publisher`
- Pod events: `kubectl describe pod -n data-sources -l app=manufacturing-data-publisher`
- Health endpoint: Test via curl as shown above
- MQTT brokers: Verify they're running and accessible
