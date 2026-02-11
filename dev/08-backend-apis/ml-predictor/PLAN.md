# ML Predictor Service - Implementation Plan

## Overview

Add machine learning capabilities to the machine pages with two core features:
1. **Time Series Prediction**: Predict future values (daily granularity, week/month horizon) using AutoGluon
2. **Multilinear Parameter Regression**: Correlate parameters across machines with parameter correlation analysis

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                              │
│  mqtt-topic-tree/app/machines/[id]/page.tsx                                 │
│  ├── Existing: Knowledge Graph, Live Telemetry, Topic Config                │
│  └── NEW: ML Insights Section (Prediction + Regression panels)              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ml-predictor Service (NEW)                          │
│  FastAPI + AutoGluon                                                        │
│  ├── /api/predict/{machine_id}        - Time series prediction              │
│  ├── /api/regression/{machine_id}     - Multilinear regression              │
│  ├── /api/correlations/{machine_id}   - Cross-machine correlations          │
│  ├── /api/train/{machine_id}          - Trigger model training              │
│  └── /health                          - Health check                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌───────────────────────────────┐     ┌───────────────────────────────────────┐
│         Neo4j Database        │     │           Cron Job (K8s)              │
│  ├── Message nodes (history)  │     │  Daily training for stale machines   │
│  ├── Prediction nodes (NEW)   │     │  Runs at 02:00 UTC                    │
│  └── Regression nodes (NEW)   │     └───────────────────────────────────────┘
└───────────────────────────────┘
```

## Data Sources

### Historical Data from Neo4j
- **Uncurated Messages**: `(Topic)-[:HAS_MESSAGE]->(Message)` where broker = "uncurated"
- **Curated Messages**: `(Topic)-[:HAS_MESSAGE]->(Message)` where broker = "curated"
- **Message Properties**: `rawPayload`, `timestamp`, `numericValue`

### Machine-Topic Mapping
- Machines define topics via `machine.topics[].topic_path` or `machine.topic_path`
- Query messages by matching topic paths in Neo4j

## New Neo4j Node Types

### Prediction Node
```cypher
(:Prediction {
  id: String,                    // UUID
  machineId: String,             // Reference to SimulatedMachine
  fieldName: String,             // e.g., "temperature"
  topicPath: String,             // Source topic
  predictionType: String,        // "time_series"
  horizon: String,               // "week" | "month"
  predictions: String,           // JSON array of {date, value, lower, upper}
  modelMetrics: String,          // JSON {rmse, mae, mape}
  trainedAt: DateTime,
  dataPointsUsed: Integer,
  expiresAt: DateTime
})

// Relationships
(m:SimulatedMachine)-[:HAS_PREDICTION]->(p:Prediction)
```

### Regression Node
```cypher
(:Regression {
  id: String,                    // UUID
  machineId: String,             // Target machine
  targetField: String,           // Field being predicted
  targetTopic: String,           // Topic of target field
  features: String,              // JSON array of {machineId, topicPath, fieldName, coefficient}
  intercept: Float,
  rSquared: Float,
  pValues: String,               // JSON object of p-values per feature
  correlationMatrix: String,     // JSON correlation matrix
  trainedAt: DateTime,
  dataPointsUsed: Integer
})

// Relationships
(m:SimulatedMachine)-[:HAS_REGRESSION]->(r:Regression)
```

## Backend Service: ml-predictor

### Directory Structure
```
/home/flexadmin/kubernetes/dev/08-backend-apis/ml-predictor/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Environment config
│   ├── api/
│   │   ├── __init__.py
│   │   ├── predictions.py      # Prediction endpoints
│   │   ├── regression.py       # Regression endpoints
│   │   └── training.py         # Training trigger endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_fetcher.py     # Neo4j data retrieval
│   │   ├── time_series.py      # AutoGluon time series
│   │   ├── regression.py       # AutoGluon tabular regression
│   │   └── storage.py          # Save/load predictions to Neo4j
│   └── models/
│       ├── __init__.py
│       └── schemas.py          # Pydantic models
└── k8s/
    ├── deployment.yaml
    ├── service.yaml
    └── cronjob.yaml
```

### Key Dependencies (requirements.txt)
```
fastapi>=0.109.0
uvicorn>=0.27.0
neo4j>=5.15.0
autogluon.timeseries>=1.0.0
autogluon.tabular>=1.0.0
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
pydantic>=2.0.0
```

### API Endpoints

#### 1. GET /api/predict/{machine_id}
Get cached predictions or trigger new prediction.

**Query Params:**
- `field`: Field name to predict (required)
- `topic`: Topic path (required for multi-topic machines)
- `horizon`: "week" | "month" (default: "week")
- `force_refresh`: boolean (default: false)

**Response:**
```json
{
  "machineId": "uuid",
  "field": "temperature",
  "topic": "factory/line1/machine1/sensors",
  "horizon": "week",
  "predictions": [
    {"date": "2026-01-12", "value": 45.2, "lower": 42.1, "upper": 48.3},
    {"date": "2026-01-13", "value": 46.1, "lower": 42.8, "upper": 49.4}
  ],
  "metrics": {"rmse": 2.3, "mae": 1.8, "mape": 4.2},
  "trainedAt": "2026-01-11T02:00:00Z",
  "dataPointsUsed": 180
}
```

#### 2. GET /api/regression/{machine_id}
Get multilinear regression analysis.

**Query Params:**
- `target_field`: Field to predict (required)
- `target_topic`: Topic path (required)
- `include_similar`: boolean - include similar machines from knowledge graph (default: true)
- `additional_machines`: comma-separated machine IDs to include
- `force_refresh`: boolean (default: false)

**Response:**
```json
{
  "machineId": "uuid",
  "targetField": "temperature",
  "targetTopic": "factory/line1/machine1/sensors",
  "features": [
    {"machineId": "uuid1", "topic": "...", "field": "pressure", "coefficient": 0.45, "pValue": 0.001},
    {"machineId": "uuid2", "topic": "...", "field": "speed", "coefficient": -0.23, "pValue": 0.02}
  ],
  "intercept": 12.5,
  "rSquared": 0.87,
  "correlationMatrix": {...},
  "trainedAt": "2026-01-11T02:00:00Z"
}
```

#### 3. POST /api/train/{machine_id}
Manually trigger model training.

**Body:**
```json
{
  "prediction": true,
  "regression": true,
  "fields": ["temperature", "pressure"]  // optional, default: all numeric fields
}
```

#### 4. GET /api/correlations/{machine_id}
Get correlation analysis with other machines.

**Query Params:**
- `field`: Field to analyze
- `source`: "similar" | "manual" | "all"
- `machine_ids`: comma-separated (for manual selection)

### AutoGluon Integration

#### Time Series Prediction
```python
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

def train_time_series(data: pd.DataFrame, field: str, horizon_days: int):
    # Resample to daily (5 points per day average)
    daily_data = data.set_index('timestamp').resample('D')[field].mean()

    ts_df = TimeSeriesDataFrame.from_data_frame(
        daily_data.reset_index(),
        id_column=None,  # Single series
        timestamp_column='timestamp'
    )

    predictor = TimeSeriesPredictor(
        prediction_length=horizon_days,
        target=field,
        eval_metric='MAPE'
    )

    predictor.fit(ts_df, time_limit=300)  # 5 min training limit
    predictions = predictor.predict(ts_df)

    return predictions
```

#### Multilinear Regression
```python
from autogluon.tabular import TabularPredictor

def train_regression(features_df: pd.DataFrame, target_col: str):
    predictor = TabularPredictor(
        label=target_col,
        problem_type='regression',
        eval_metric='r2'
    )

    predictor.fit(features_df, time_limit=300)

    # Extract feature importance and coefficients
    importance = predictor.feature_importance(features_df)

    return predictor, importance
```

## Frontend Changes

### New Components

#### 1. MLInsightsSection.tsx
Container component for the ML features section.

```
/components/machines/
├── MLInsightsSection.tsx       # Main container
├── PredictionPanel.tsx         # Time series prediction UI
├── RegressionPanel.tsx         # Regression analysis UI
└── CorrelationSelector.tsx     # Machine/field selector for regression
```

#### 2. PredictionPanel.tsx
- Field selector dropdown
- Horizon selector (Week/Month)
- Line chart showing historical + predicted values with confidence intervals
- Model metrics display (RMSE, MAE, MAPE)
- "Refresh Prediction" button
- Loading/error states

#### 3. RegressionPanel.tsx
- Target field selector
- Correlation source toggle (Similar Machines / Manual Selection)
- Machine multi-select for manual mode
- Results display:
  - R² score
  - Feature coefficients table with p-values
  - Correlation heatmap visualization
- "Run Analysis" button

### API Integration

New file: `/lib/ml-api.ts`
```typescript
const ML_API_BASE = process.env.NEXT_PUBLIC_ML_API_URL || 'http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_3';

export async function getPrediction(machineId: string, params: PredictionParams): Promise<PredictionResult>;
export async function getRegression(machineId: string, params: RegressionParams): Promise<RegressionResult>;
export async function triggerTraining(machineId: string, options: TrainingOptions): Promise<void>;
export async function getCorrelations(machineId: string, params: CorrelationParams): Promise<CorrelationResult>;
```

### Page Layout Update

In `app/machines/[id]/page.tsx`, add below Topic Configuration:

```tsx
{/* ML Insights Section */}
<div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
  {/* Prediction Panel */}
  <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <PredictionPanel machine={machine} />
  </div>

  {/* Regression Panel */}
  <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <RegressionPanel machine={machine} />
  </div>
</div>
```

## Kubernetes Deployment

### CronJob for Daily Training
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ml-predictor-daily-training
  namespace: backend-apis
spec:
  schedule: "0 2 * * *"  # 02:00 UTC daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: trainer
            image: localhost:5000/ml-predictor:latest
            command: ["python", "-m", "src.jobs.daily_training"]
            env:
              - name: NEO4J_URI
                valueFrom:
                  secretKeyRef:
                    name: neo4j-credentials
                    key: uri
          restartPolicy: OnFailure
```

### Service Configuration
- Namespace: `backend-apis`
- Port: 8000
- Resource limits: 4Gi memory (AutoGluon is memory-intensive)

## Implementation Steps

### Phase 1: Backend Service Setup
1. Create ml-predictor directory structure
2. Implement config.py with Neo4j connection
3. Implement data_fetcher.py to query historical messages
4. Create basic FastAPI app with health endpoint
5. Add Dockerfile and k8s manifests
6. Deploy and verify connectivity

### Phase 2: Time Series Prediction
1. Implement time_series.py with AutoGluon integration
2. Create predictions.py API endpoints
3. Implement storage.py for Neo4j Prediction nodes
4. Add daily aggregation logic (5 points/day → 1 daily average)
5. Test with sample machine data

### Phase 3: Regression Analysis
1. Implement regression.py with AutoGluon tabular
2. Add correlation matrix calculation
3. Integrate with similarity_results for related machines
4. Create regression.py API endpoints
5. Store results in Neo4j Regression nodes

### Phase 4: Frontend Components
1. Create ml-api.ts client library
2. Implement PredictionPanel.tsx with Chart.js
3. Implement RegressionPanel.tsx with correlation heatmap
4. Add CorrelationSelector.tsx for machine selection
5. Integrate MLInsightsSection into machine detail page

### Phase 5: Cron Job & Polish
1. Implement daily_training.py job script
2. Create CronJob manifest
3. Add stale prediction detection logic
4. Add manual refresh functionality
5. Error handling and loading states

## Verification Plan

1. **Backend Health**: `curl http://ml-predictor.backend-apis:YOUR_API_PORT_3/health`
2. **Data Fetch**: Verify historical data retrieval from Neo4j
3. **Prediction**: Trigger prediction for a running machine, verify response
4. **Regression**: Run regression with similar machines, verify coefficients
5. **Frontend**: Navigate to machine page, verify ML panels render
6. **Cron**: Check CronJob logs after scheduled run
7. **Manual Refresh**: Click refresh button, verify new predictions generated

## Notes

- AutoGluon requires significant memory (~4GB) for training
- Initial training may take 5-10 minutes per machine
- Predictions are cached and only regenerated daily or on manual trigger
- Feature selection for regression automatically includes similar machines from knowledge graph
- Both uncurated and curated broker data are used for training
