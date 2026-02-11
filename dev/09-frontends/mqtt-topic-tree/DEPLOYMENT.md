# MQTT Topic Tree - Deployment Guide

Quick reference guide for deploying the MQTT Topic Tree Explorer to Kubernetes.

## Prerequisites

Before deploying, ensure you have:

- [ ] Kubernetes cluster running (K3s)
- [ ] Docker installed and running
- [ ] kubectl configured and connected to cluster
- [ ] EMQX broker deployed in `emqx-curated` namespace
- [ ] Access to build Docker images

## Quick Deployment

### 1. Build Docker Image

```bash
cd /home/flexadmin/kubernetes/dev/09-frontends/mqtt-topic-tree

# Build the image
docker build -t mqtt-topic-tree:latest .

# Verify the image
docker images | grep mqtt-topic-tree
```

Expected output:
```
mqtt-topic-tree   latest   <image-id>   <timestamp>   <size>
```

### 2. Deploy to Kubernetes

Apply the manifests in order:

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Create deployment
kubectl apply -f deployment.yaml

# Create service
kubectl apply -f service.yaml

# Create ingress (optional)
kubectl apply -f ingress.yaml
```

### 3. Verify Deployment

Run the test script:

```bash
./tests/test-mqtt-topic-tree.sh
```

Or manually verify:

```bash
# Check namespace
kubectl get namespace frontends

# Check deployment
kubectl get deployment -n frontends

# Check pods
kubectl get pods -n frontends

# Check service
kubectl get svc -n frontends

# Check logs
kubectl logs -n frontends -l app=mqtt-topic-tree -f
```

### 4. Access the Dashboard

#### Option A: NodePort (Development)

The application is accessible via NodePort on port 30800:

```bash
# Get node IP
kubectl get nodes -o wide

# Access via browser
http://<node-ip>:30800
```

#### Option B: Port Forward (Development)

```bash
# Forward port 8080 locally to service port 3000
kubectl port-forward -n frontends svc/mqtt-topic-tree 8080:YOUR_FRONTEND_PORT

# Access via browser
http://localhost:YOUR_API_PORT
```

#### Option C: Traefik Ingress (Production)

If you have Traefik configured with a custom entry point:

1. Update `ingress.yaml` with your entry point name
2. Apply the ingress route
3. Access via your configured domain/path

## Configuration

### Environment Variables

Default configuration is set in `deployment.yaml`:

```yaml
env:
- name: MQTT_BROKER_WS_URL
  value: "ws://YOUR_MQTT_CURATED_HOST:YOUR_MQTT_WS_PORT/mqtt"
- name: MQTT_USERNAME
  value: "YOUR_MQTT_USERNAME"
- name: MQTT_PASSWORD
  value: "YOUR_MQTT_PASSWORD"
```

To use a different broker or credentials, edit `deployment.yaml` before applying.

### Resource Limits

Default resource allocation:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

Adjust based on your cluster capacity and expected load.

## Verification Steps

### 1. Check Pod Health

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n frontends -l app=mqtt-topic-tree -o jsonpath='{.items[0].metadata.name}')

# Check pod status
kubectl get pod -n frontends $POD_NAME

# Check pod events
kubectl describe pod -n frontends $POD_NAME

# View logs
kubectl logs -n frontends $POD_NAME
```

Expected log output:
```
[MQTT] Initializing MQTT client...
[MQTT] Broker URL: ws://YOUR_MQTT_CURATED_HOST:YOUR_MQTT_WS_PORT/mqtt
[MQTT] Connected to broker
[MQTT] Subscribed to all topics (#)
[MQTT] Successfully connected and subscribed
```

### 2. Test Health Endpoint

```bash
# From outside the pod
kubectl port-forward -n frontends svc/mqtt-topic-tree 3000:YOUR_FRONTEND_PORT
curl http://localhost:YOUR_FRONTEND_PORT/health

# From inside the pod
kubectl exec -n frontends $POD_NAME -- wget -q -O- http://localhost:YOUR_FRONTEND_PORT/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": 1700000000000,
  "service": "mqtt-topic-tree",
  "version": "1.0.0"
}
```

### 3. Test MQTT Connection

Verify the pod can reach the MQTT broker:

```bash
# DNS resolution
kubectl exec -n frontends $POD_NAME -- nslookup YOUR_MQTT_CURATED_HOST

# Network connectivity
kubectl exec -n frontends $POD_NAME -- wget -q -O- http://YOUR_MQTT_CURATED_HOST:YOUR_EMQX_DASHBOARD_PORT/status
```

### 4. Verify Topics Display

1. Ensure data publishers are running:
```bash
kubectl get pods -n data-sources
```

2. Check if manufacturing data publisher is sending messages:
```bash
kubectl logs -n data-sources -l app=manufacturing-data-publisher --tail=10
```

3. Access the dashboard and verify:
   - Connection status shows "Connected"
   - Topic count increases over time
   - Topics appear in the tree view
   - Selecting a topic shows message details

## Troubleshooting

### Issue: Pod Not Starting

**Symptoms**: Pod in CrashLoopBackOff or ImagePullBackOff

**Solutions**:

1. Check image exists:
```bash
docker images | grep mqtt-topic-tree
```

2. Verify image pull policy:
```bash
kubectl get deployment mqtt-topic-tree -n frontends -o yaml | grep imagePullPolicy
```
Should be `IfNotPresent` for local images.

3. Check pod events:
```bash
kubectl describe pod -n frontends <pod-name>
```

### Issue: Health Check Failing

**Symptoms**: Pod restarts repeatedly, readiness probe fails

**Solutions**:

1. Increase initial delay:
```yaml
readinessProbe:
  initialDelaySeconds: 60  # Increase if needed
```

2. Test health endpoint manually:
```bash
kubectl exec -n frontends $POD_NAME -- wget -q -O- http://localhost:YOUR_FRONTEND_PORT/health
```

3. Check application logs for startup errors

### Issue: Cannot Connect to MQTT Broker

**Symptoms**: Dashboard shows "Disconnected", logs show connection errors

**Solutions**:

1. Verify EMQX broker is running:
```bash
kubectl get pods -n emqx-curated
kubectl get svc -n emqx-curated
```

2. Test DNS resolution:
```bash
kubectl exec -n frontends $POD_NAME -- nslookup YOUR_MQTT_CURATED_HOST
```

3. Check network policies (if any):
```bash
kubectl get networkpolicies -A
```

4. Verify credentials are correct in deployment.yaml

5. Check EMQX logs:
```bash
kubectl logs -n emqx-curated -l app=emqx -f
```

### Issue: No Topics Appearing

**Symptoms**: Dashboard connected but topic tree is empty

**Solutions**:

1. Verify MQTT messages are being published:
```bash
# Check data publishers
kubectl get pods -n data-sources

# Check publisher logs
kubectl logs -n data-sources -l app=manufacturing-data-publisher
```

2. Check application logs for subscription confirmation:
```bash
kubectl logs -n frontends $POD_NAME | grep -i "subscribed"
```

3. Test MQTT subscription manually (if mosquitto-clients available):
```bash
mosquitto_sub -h <broker-ip> -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD -t '#' -v
```

### Issue: High Memory Usage

**Symptoms**: Pod OOMKilled, high memory consumption

**Solutions**:

1. Check current usage:
```bash
kubectl top pod -n frontends
```

2. Increase memory limits in deployment.yaml:
```yaml
resources:
  limits:
    memory: "2Gi"  # Increase as needed
```

3. Monitor topic count - memory grows with unique topics

4. Consider implementing topic filtering if too many topics

### Issue: Ingress Not Working

**Symptoms**: Cannot access via Traefik ingress

**Solutions**:

1. Check if Traefik is running:
```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik
```

2. Verify IngressRoute was created:
```bash
kubectl get ingressroute -n frontends
```

3. Check Traefik entry point exists:
```bash
kubectl describe deployment traefik -n kube-system | grep entrypoints
```

4. Use NodePort or port-forward as alternative

## Updating the Application

### Update Code

1. Make changes to source code
2. Rebuild Docker image:
```bash
docker build -t mqtt-topic-tree:latest .
```

3. Delete and recreate pod:
```bash
kubectl delete pod -n frontends -l app=mqtt-topic-tree
```

New pod will automatically be created with updated image.

### Update Configuration

1. Edit deployment.yaml
2. Apply changes:
```bash
kubectl apply -f deployment.yaml
```

3. Verify rollout:
```bash
kubectl rollout status deployment/mqtt-topic-tree -n frontends
```

## Scaling

To run multiple replicas:

```bash
kubectl scale deployment mqtt-topic-tree -n frontends --replicas=3
```

**Note**: Each replica maintains its own MQTT connection and topic tree state. Consider adding shared state (Redis) if multiple replicas needed.

## Cleanup

To remove the application:

```bash
# Delete all resources
kubectl delete -f ingress.yaml
kubectl delete -f service.yaml
kubectl delete -f deployment.yaml

# Optional: Delete namespace (if no other apps)
kubectl delete -f namespace.yaml
```

## Production Considerations

Before deploying to production:

- [ ] Use Kubernetes Secrets for MQTT credentials
- [ ] Configure resource limits based on load testing
- [ ] Set up proper ingress with TLS
- [ ] Configure authentication for dashboard access
- [ ] Set up monitoring and alerting
- [ ] Implement log aggregation
- [ ] Use wss:// instead of ws:// for MQTT
- [ ] Configure backup and disaster recovery
- [ ] Document runbook for common issues
- [ ] Set up CI/CD pipeline for automated deployments

## Monitoring

### Prometheus Metrics (Future)

Add Prometheus annotations to deployment:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "3000"
    prometheus.io/path: "/metrics"
```

### Log Aggregation

Forward logs to centralized logging:

```bash
# Example: Fluentd, Elasticsearch, Kibana
kubectl logs -n frontends -l app=mqtt-topic-tree | forward-to-elk
```

## Support

For deployment issues:

1. Run automated test: `./tests/test-mqtt-topic-tree.sh`
2. Check application logs
3. Review pod events
4. Verify prerequisites
5. Consult README.md for architecture details

## Quick Reference

```bash
# Common commands
kubectl get all -n frontends
kubectl logs -n frontends -l app=mqtt-topic-tree -f
kubectl describe pod -n frontends <pod-name>
kubectl exec -n frontends <pod-name> -- sh
kubectl port-forward -n frontends svc/mqtt-topic-tree 8080:YOUR_FRONTEND_PORT

# Restart application
kubectl rollout restart deployment/mqtt-topic-tree -n frontends

# View resource usage
kubectl top pod -n frontends

# Delete and redeploy
kubectl delete -f deployment.yaml && kubectl apply -f deployment.yaml
```
