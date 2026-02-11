# MQTT Topic Tree Explorer

A modern, real-time dashboard for exploring and visualizing MQTT topic hierarchies. Built with Next.js 14, React, and TypeScript, this application provides an intuitive tree view of your MQTT broker's topics with live updates and detailed message inspection.

## Features

- **Real-time Topic Discovery**: Automatically discovers and displays all MQTT topics as they receive messages
- **Interactive Tree View**: Expandable/collapsible hierarchical topic visualization
- **Message Inspection**: View message payloads, timestamps, and message counts for each topic
- **Live Statistics**: Real-time metrics including total topics, messages, and last update time
- **Connection Monitoring**: Visual connection status indicator with auto-reconnect
- **Modern UI**: Clean, responsive interface built with Tailwind CSS
- **Server-Sent Events**: Efficient real-time updates using SSE
- **Health Monitoring**: Built-in health check endpoint for Kubernetes probes

## Architecture

### Technology Stack

- **Frontend**: Next.js 14 (App Router), React 18, TypeScript
- **Styling**: Tailwind CSS
- **MQTT Client**: MQTT.js (WebSocket connection)
- **Testing**: Playwright for E2E tests
- **Container**: Docker multi-stage build
- **Orchestration**: Kubernetes (K3s)

### Application Flow

```
Browser Client
    ↓
Next.js Frontend (SSE)
    ↓
API Route (/api/mqtt)
    ↓
MQTT.js Client (WebSocket)
    ↓
EMQX Broker (emqx-curated)
```

### Directory Structure

```
mqtt-topic-tree/
├── app/                      # Next.js App Router
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Main dashboard page
│   ├── globals.css          # Global styles
│   ├── health/route.ts      # Health check endpoint
│   └── api/mqtt/route.ts    # SSE endpoint for MQTT data
├── components/
│   ├── Dashboard.tsx        # Main dashboard component
│   └── TopicNode.tsx        # Recursive tree node component
├── lib/
│   ├── mqtt-client.ts       # MQTT client wrapper
│   └── topic-tree-builder.ts # Topic hierarchy builder
├── tests/
│   ├── e2e/                 # Playwright E2E tests
│   │   ├── dashboard.spec.ts
│   │   └── playwright.config.ts
│   └── test-mqtt-topic-tree.sh # Kubernetes deployment test
├── Dockerfile               # Multi-stage Docker build
├── deployment.yaml          # Kubernetes deployment
├── service.yaml             # Kubernetes service
├── ingress.yaml             # Traefik ingress route
├── namespace.yaml           # Kubernetes namespace
└── package.json             # Node.js dependencies
```

## Configuration

### Environment Variables

The application uses the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER_WS_URL` | `ws://YOUR_MQTT_CURATED_HOST:YOUR_MQTT_WS_PORT/mqtt` | MQTT broker WebSocket URL |
| `MQTT_USERNAME` | `YOUR_MQTT_USERNAME` | MQTT broker username |
| `MQTT_PASSWORD` | `YOUR_MQTT_PASSWORD` | MQTT broker password |
| `NODE_ENV` | `production` | Node environment |
| `PORT` | `YOUR_FRONTEND_PORT` | Application port |

### MQTT Broker Connection

The application connects to the EMQX curated broker in the cluster:

- **Service**: `YOUR_MQTT_CURATED_HOST`
- **Port**: 8083 (WebSocket)
- **Protocol**: MQTT over WebSocket
- **Subscription**: `#` (all topics)

## Development

### Prerequisites

- Node.js 18+
- npm or yarn
- Docker (for containerization)
- kubectl (for Kubernetes deployment)
- Access to MQTT broker

### Local Development

1. Install dependencies:
```bash
npm install
```

2. Set environment variables (create `.env.local`):
```bash
MQTT_BROKER_WS_URL=ws://localhost:YOUR_MQTT_WS_PORT/mqtt
MQTT_USERNAME="YOUR_MQTT_USERNAME"
MQTT_PASSWORD="YOUR_MQTT_PASSWORD"
```

3. Run development server:
```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:YOUR_FRONTEND_PORT)

### Running Tests

#### Unit/Integration Tests (Playwright)

```bash
# Install Playwright browsers
npx playwright install

# Run tests
npm test

# Run tests with UI
npm run test:ui

# Run tests in headed mode
npm run test:headed
```

### Building for Production

```bash
npm run build
npm start
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

### Quick Start

1. Build Docker image:
```bash
docker build -t mqtt-topic-tree:latest .
```

2. Apply Kubernetes manifests:
```bash
kubectl apply -f namespace.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
```

3. Verify deployment:
```bash
./tests/test-mqtt-topic-tree.sh
```

## Usage

### Dashboard Overview

The dashboard consists of two main panels:

#### Topic Tree Panel (Left)
- Hierarchical view of all MQTT topics
- Folder icons represent topic branches
- Document icons represent leaf topics (with messages)
- Numbers in parentheses show message count
- Click arrows to expand/collapse branches
- Click topics to view details

#### Topic Details Panel (Right)
- Full topic path
- Message count
- Last message timestamp
- Message payload (formatted JSON if applicable)

### Accessing the Application

Once deployed, you can access the dashboard via:

1. **NodePort** (development):
```bash
http://<node-ip>:30800
```

2. **Port Forward** (development):
```bash
kubectl port-forward -n frontends svc/mqtt-topic-tree 8080:YOUR_FRONTEND_PORT
# Visit http://localhost:YOUR_API_PORT
```

3. **Traefik Ingress** (production):
```bash
# Configure Traefik IngressRoute and access via your domain
```

## Monitoring

### Health Check

The application exposes a health check endpoint:

```bash
curl http://localhost:YOUR_FRONTEND_PORT/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": 1700000000000,
  "service": "mqtt-topic-tree",
  "version": "1.0.0"
}
```

### Logs

View application logs:
```bash
kubectl logs -n frontends -l app=mqtt-topic-tree -f
```

### Metrics

Monitor the following:
- Pod status and restarts
- Memory and CPU usage
- MQTT connection status (in logs)
- HTTP request latency
- SSE connection count

## Troubleshooting

### MQTT Connection Issues

If the dashboard shows "Disconnected":

1. Check MQTT broker is running:
```bash
kubectl get pods -n emqx-curated
```

2. Verify service DNS resolution:
```bash
kubectl exec -n frontends <pod-name> -- nslookup YOUR_MQTT_CURATED_HOST
```

3. Test MQTT connectivity:
```bash
kubectl exec -n frontends <pod-name> -- wget -O- http://YOUR_MQTT_CURATED_HOST:YOUR_EMQX_DASHBOARD_PORT
```

### No Topics Showing

If topics don't appear:

1. Verify MQTT messages are being published:
```bash
kubectl logs -n data-sources -l app=manufacturing-data-publisher
```

2. Check application logs for subscription confirmation:
```bash
kubectl logs -n frontends -l app=mqtt-topic-tree | grep "Subscribed"
```

### Pod Not Starting

1. Check pod events:
```bash
kubectl describe pod -n frontends <pod-name>
```

2. Check image availability:
```bash
docker images | grep mqtt-topic-tree
```

3. Verify resource limits aren't exceeded

## Performance Considerations

- **Topic Tree Updates**: Tree is rebuilt and sent to clients every 2 seconds
- **Memory Usage**: Grows with number of unique topics (typically ~500MB for 1000 topics)
- **Message Payload**: Truncated to 200 characters in tree structure
- **WebSocket Connections**: One per backend instance to MQTT broker
- **SSE Connections**: One per connected browser client

## Security Considerations

- MQTT credentials are stored as environment variables (consider using Kubernetes Secrets)
- No authentication on the dashboard (add reverse proxy auth if needed)
- WebSocket connections are unencrypted (ws:// not wss://)
- CORS is not configured (same-origin only)

## Future Enhancements

- [ ] Topic filtering and search
- [ ] Historical message viewer
- [ ] Message publishing capability
- [ ] Support for multiple broker connections
- [ ] User authentication and authorization
- [ ] Dark mode support
- [ ] Export topic tree as JSON/CSV
- [ ] Message rate monitoring
- [ ] Custom topic retention rules
- [ ] Alert configuration for topic patterns

## Contributing

When contributing to this project:

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Test in Kubernetes environment
5. Verify health checks pass

## License

This project is part of the manufacturing data platform.

## Support

For issues and questions:
- Check application logs
- Review Kubernetes events
- Inspect MQTT broker status
- Refer to DEPLOYMENT.md for setup issues
