# Manufacturing Data Publisher

A Python-based data source simulator that publishes realistic manufacturing data from 100 machine assets and 50 enterprise system assets to MQTT brokers.

## Overview

This application simulates a complete smart manufacturing environment by publishing data from various industrial assets including:

- **100 Machine Assets**: CNC machines, robots, conveyors, welders, presses, AGVs, grinders, laser cutters, 3D printers, and assembly stations
- **50 Enterprise Systems**: ERP, MES, SCADA, DCS, WMS, AGV/AMR controllers, quality systems, and maintenance systems

Data is published to both curated and uncurated MQTT brokers using a mix of UNS (Unified Namespace) and flat topic structures.

## Architecture

```
manufacturing-data-publisher/
├── src/
│   ├── main.py                    # Application entry point
│   ├── config.py                  # Configuration management
│   ├── publishers/
│   │   ├── machine_publisher.py   # Machine asset data publisher
│   │   └── enterprise_publisher.py # Enterprise system data publisher
│   ├── models/
│   │   ├── machine_models.py      # Machine data models & simulators
│   │   └── enterprise_models.py   # Enterprise system models & simulators
│   └── utils/
│       └── mqtt_client.py         # MQTT client wrapper
├── Dockerfile                     # Container image definition
├── requirements.txt               # Python dependencies
├── namespace.yaml                 # Kubernetes namespace
├── deployment.yaml                # Kubernetes deployment
├── service.yaml                   # Kubernetes service
├── ingress.yaml                   # Traefik ingress route
└── tests/
    └── test-data-publisher.sh     # Deployment test script
```

## Machine Assets (100 Total)

| Type | Count | Metrics Published |
|------|-------|-------------------|
| CNC Mills | 15 | Temperature, vibration, spindle speed, power, cycle count, OEE |
| Robots | 12 | Temperature, vibration, cycles/hour, power, good/bad parts |
| Conveyors | 10 | Speed, temperature, power, runtime |
| Welders | 8 | Temperature, welds/hour, power, quality metrics |
| Presses | 8 | Stroke rate, temperature, vibration, force |
| AGVs | 6 | Speed, battery, position, missions completed |
| CNC Lathes | 6 | RPM, temperature, vibration, power |
| Mills | 6 | RPM, temperature, power, cycle count |
| Grinders | 5 | RPM, temperature, vibration, power |
| Laser Cutters | 5 | Cuts/hour, temperature, power |
| 3D Printers | 4 | Print speed, hotend temp, layer progress |
| Assembly Stations | 15 | Units/hour, temperature, cycle time |

## Enterprise Systems (50 Total)

| Type | Count | Vendors |
|------|-------|---------|
| ERP | 5 | SAP, Oracle, Microsoft Dynamics, Infor, Epicor |
| MES | 8 | Wonderware, Rockwell FactoryTalk, Siemens Opcenter, Parsec, AVEVA |
| SCADA | 10 | Ignition, Wonderware, Siemens WinCC, GE iFIX, Rockwell |
| DCS | 8 | Siemens PCS7, Honeywell Experion, Emerson DeltaV, ABB 800xA |
| WMS | 4 | Manhattan, Blue Yonder, SAP EWM, Oracle WMS |
| AGV Controllers | 5 | Balyo, Seegrid, Fetch Robotics, MiR Fleet, AutoGuide |
| Quality Systems | 5 | InfinityQS, Minitab, ETQ Reliance, MasterControl, Arena QMS |
| Maintenance Systems | 5 | IBM Maximo, SAP PM, Infor EAM, Fiix, eMaint |

## MQTT Topic Structures

### UNS Topics (ISA-95 Hierarchy)
```
enterprise/site/area/line/cell/asset_id/metric
enterprise/systems/system_type/system_id/metric
```

**Examples:**
```
acme-manufacturing/plant-01/machining/line-a/cell-03/cnc_mill_001/telemetry
acme-manufacturing/plant-01/assembly/line-b/cell-01/robot_045/state
acme-manufacturing/systems/mes/mes_003/data
acme-manufacturing/systems/scada/scada_007/status
```

### Flat Topics (Legacy Systems)
```
machine/asset_id/metric
system_type/system_id/metric
```

**Examples:**
```
machine/cnc_mill_001/temperature
machine/robot_045/state
mes/mes_003/data
scada/scada_007/alarms
```

## Data Characteristics

### Machine Telemetry
- **State machine simulation**: startup → running → idle → maintenance → fault
- **Realistic sensor data**: Temperature drift, vibration patterns, correlated metrics
- **Production metrics**: Cycle counts, good/bad parts, OEE calculations
- **Publishing intervals**: 1-10 seconds (configurable)

### Enterprise System Data
- **System health**: CPU, memory, response time, active connections
- **Business metrics**: Work orders, inventory, shipments, alarms
- **Operational data**: Active processes, pending tasks, KPIs
- **Publishing intervals**: 5-60 seconds (configurable)

## MQTT Broker Strategy

### Curated Broker (`emqx-curated`)
- Aggregated telemetry data
- Validated and clean data
- Retained messages for last known state
- Primary data source for applications

### Uncurated Broker (`emqx-uncurated`)
- All raw telemetry and state changes
- Individual metric topics for granular access
- High-frequency updates
- Data lake / historian ingestion

## Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER_CURATED_HOST` | `YOUR_MQTT_CURATED_HOST` | Curated broker hostname |
| `MQTT_BROKER_CURATED_PORT` | `YOUR_MQTT_PORT` | Curated broker port |
| `MQTT_BROKER_UNCURATED_HOST` | `YOUR_MQTT_UNCURATED_HOST` | Uncurated broker hostname |
| `MQTT_BROKER_UNCURATED_PORT` | `YOUR_MQTT_PORT` | Uncurated broker port |
| `MQTT_USERNAME` | `YOUR_MQTT_USERNAME` | MQTT username |
| `MQTT_PASSWORD` | `YOUR_MQTT_PASSWORD` | MQTT password |
| `MQTT_QOS` | `1` | Quality of Service (0, 1, or 2) |
| `HEALTH_CHECK_PORT` | `YOUR_API_PORT_2` | Health endpoint port |
| `NUM_MACHINES` | `100` | Number of machine assets |
| `NUM_ENTERPRISE_SYSTEMS` | `50` | Number of enterprise systems |
| `MACHINE_PUBLISH_INTERVAL_MIN` | `1.0` | Min publish interval (seconds) |
| `MACHINE_PUBLISH_INTERVAL_MAX` | `10.0` | Max publish interval (seconds) |
| `ENTERPRISE_PUBLISH_INTERVAL_MIN` | `5.0` | Min publish interval (seconds) |
| `ENTERPRISE_PUBLISH_INTERVAL_MAX` | `60.0` | Max publish interval (seconds) |
| `ENTERPRISE` | `acme-manufacturing` | Enterprise name (ISA-95) |
| `SITE` | `plant-01` | Site name (ISA-95) |

## Deployment

### Prerequisites
- Kubernetes cluster (K3s)
- Docker
- kubectl
- EMQX brokers running (curated and uncurated)

### Build and Deploy
```bash
# Navigate to application directory
cd /home/flexadmin/kubernetes/dev/06-data-sources/manufacturing-data-publisher

# Build Docker image
docker build -t manufacturing-data-publisher:latest .

# Deploy to Kubernetes
kubectl apply -f namespace.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# Check deployment status
kubectl get pods -n data-sources
kubectl logs -n data-sources -l app=manufacturing-data-publisher -f
```

### Using the Test Script
```bash
cd /home/flexadmin/kubernetes/dev/06-data-sources/manufacturing-data-publisher
./tests/test-data-publisher.sh
```

The test script will:
1. Build the Docker image
2. Apply all Kubernetes manifests
3. Wait for deployment readiness
4. Verify health endpoint
5. Check MQTT connectivity
6. Display application logs
7. Show access information

## Health Endpoint

**URL**: `http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_2/health`

**Response Format**:
```json
{
  "status": "healthy",
  "timestamp": 1234567890123,
  "machine_stats": {
    "total_machines": 100,
    "active_threads": 100,
    "state_distribution": {
      "running": 75,
      "idle": 15,
      "maintenance": 5,
      "fault": 3,
      "startup": 2
    },
    "curated_connected": true,
    "uncurated_connected": true
  },
  "enterprise_stats": {
    "total_systems": 50,
    "active_threads": 50,
    "system_type_distribution": {
      "erp": 5,
      "mes": 8,
      "scada": 10,
      "dcs": 8,
      "wms": 4,
      "agv_controller": 5,
      "quality_system": 5,
      "maintenance_system": 5
    },
    "curated_connected": true,
    "uncurated_connected": true
  }
}
```

## Monitoring MQTT Data

### Subscribe to All Topics
```bash
# From inside the cluster
kubectl run -n emqx-curated -it --rm mqtt-client --image=eclipse-mosquitto:latest --restart=Never -- \
  mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD -t '#' -v
```

### Subscribe to Specific Topics
```bash
# All machine telemetry (UNS)
mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD \
  -t 'acme-manufacturing/plant-01/+/+/+/+/telemetry' -v

# All enterprise systems (UNS)
mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD \
  -t 'acme-manufacturing/systems/#' -v

# All flat topics
mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD \
  -t 'machine/#' -v

# Specific machine
mosquitto_sub -h emqx-broker -p 1883 -u YOUR_MQTT_USERNAME -P YOUR_MQTT_PASSWORD \
  -t 'machine/cnc_mill_001/#' -v
```

## External Access via Traefik

To expose the health endpoint externally via Traefik LoadBalancer:

1. Edit Traefik service:
```bash
kubectl edit svc traefik -n kube-system
```

2. Add port configuration:
```yaml
ports:
- name: datasources
  nodePort: 30XXX  # Will be auto-assigned
  port: YOUR_API_PORT_2
  protocol: TCP
  targetPort: datasources
```

3. Add entrypoint to Traefik deployment:
```bash
kubectl edit deployment traefik -n kube-system
```

Add to args:
```yaml
- --entrypoints.datasources.address=:YOUR_API_PORT_2
```

4. Access via LoadBalancer IP:
```bash
curl http://YOUR_REGISTRY_IP:YOUR_API_PORT_2/health
```

## Troubleshooting

### Check Pod Status
```bash
kubectl get pods -n data-sources
kubectl describe pod -n data-sources <pod-name>
```

### View Logs
```bash
kubectl logs -n data-sources -l app=manufacturing-data-publisher -f
```

### Test Health Endpoint
```bash
POD_NAME=$(kubectl get pods -n data-sources -l app=manufacturing-data-publisher -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n data-sources ${POD_NAME} -- curl http://localhost:YOUR_API_PORT_2/health
```

### Check MQTT Connectivity
```bash
# View logs for connection messages
kubectl logs -n data-sources -l app=manufacturing-data-publisher | grep "MQTT"
```

### Port Forward for Local Testing
```bash
kubectl port-forward -n data-sources svc/manufacturing-data-publisher 8090:YOUR_API_PORT_2
curl http://localhost:YOUR_API_PORT_2/health
```

## Resource Usage

**Configured Resources**:
- CPU Request: 500m (0.5 cores)
- CPU Limit: 1000m (1 core)
- Memory Request: 512Mi
- Memory Limit: 1Gi

**Typical Usage** (150 publishing threads):
- CPU: 200-400m
- Memory: 300-500Mi

## Cleanup

### Delete Application
```bash
kubectl delete -f /home/flexadmin/kubernetes/dev/06-data-sources/manufacturing-data-publisher/deployment.yaml
kubectl delete -f /home/flexadmin/kubernetes/dev/06-data-sources/manufacturing-data-publisher/service.yaml
kubectl delete -f /home/flexadmin/kubernetes/dev/06-data-sources/manufacturing-data-publisher/ingress.yaml
```

### Delete Namespace (removes everything)
```bash
kubectl delete namespace data-sources
```

## License

Internal use only - ACME Manufacturing

## Support

For issues or questions, contact the DevOps team.
