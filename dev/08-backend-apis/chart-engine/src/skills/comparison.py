import json
from typing import Optional
from .base import ChartSkill, get_color, parse_time_window


class BarComparisonSkill(ChartSkill):
    """Bar chart for comparing values across categories."""

    def __init__(self):
        self.id = "bar_comparison"
        self.name = "Bar Comparison Chart"
        self.description = "Compare values across different topics or categories using bars. Best for showing relative differences between discrete items."
        self.category = "comparison"
        self.chart_type = "bar"
        self.supports_streaming = True
        self.parameters_schema = {
            "type": "object",
            "required": ["topics", "field"],
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Topics to compare"
                },
                "field": {
                    "type": "string",
                    "description": "Field to compare"
                },
                "groupBy": {
                    "type": "string",
                    "enum": ["topic", "time"],
                    "default": "topic",
                    "description": "How to group the bars"
                },
                "aggregation": {
                    "type": "string",
                    "enum": ["latest", "avg", "min", "max", "sum"],
                    "default": "latest"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        topics = params["topics"]
        aggregation = params.get("aggregation", "latest")

        if aggregation == "latest":
            query = """
            MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
            WHERE t.path IN $topics
            WITH t, m
            ORDER BY m.timestamp DESC
            WITH t, collect(m)[0] AS latest
            RETURN t.path AS topic,
                   latest.rawPayload AS payload,
                   latest.timestamp AS timestamp,
                   latest.numericValue AS numericValue
            """
        else:
            agg_func = aggregation.upper()
            query = f"""
            MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
            WHERE t.path IN $topics
              AND m.timestamp > datetime() - duration({{hours: 1}})
            RETURN t.path AS topic,
                   {agg_func}(m.numericValue) AS aggregatedValue
            """

        return query, {"topics": topics}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        field = params["field"]
        aggregation = params.get("aggregation", "latest")

        labels = []
        values = []

        for record in data:
            topic = record.get("topic", "")
            # Use short name for label
            short_name = topic.split("/")[-1] if "/" in topic else topic
            labels.append(short_name)

            if aggregation == "latest":
                payload = record.get("payload", {})
                # Parse JSON string payload if needed
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = None

                # Extract value - handle both dict payloads and raw numeric payloads
                value = None
                if isinstance(payload, dict) and field in payload:
                    value = payload[field]
                elif isinstance(payload, (int, float)):
                    value = payload  # Raw numeric payload
                elif record.get("numericValue") is not None:
                    value = record.get("numericValue")

                values.append(value if value is not None else 0)
            else:
                values.append(record.get("aggregatedValue", 0))

        return {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": field,
                    "data": values,
                    "backgroundColor": [get_color(i, 0.7) for i in range(len(values))],
                    "borderColor": [get_color(i) for i in range(len(values))],
                    "borderWidth": 1
                }]
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Comparison: {field}"
                    }
                },
                "scales": {
                    "y": {
                        "beginAtZero": True
                    }
                }
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        return params.get("topics", [])


class ScatterCorrelationSkill(ChartSkill):
    """Scatter plot for showing correlation between two variables."""

    def __init__(self):
        self.id = "scatter_correlation"
        self.name = "Scatter Plot"
        self.description = "Show relationship between two variables as points on X-Y axes. Best for identifying correlations, clusters, and outliers."
        self.category = "comparison"
        self.chart_type = "scatter"
        self.supports_streaming = True
        self.parameters_schema = {
            "type": "object",
            "required": ["x_topic", "x_field", "y_topic", "y_field"],
            "properties": {
                "x_topic": {
                    "type": "string",
                    "description": "Topic for X-axis values"
                },
                "x_field": {
                    "type": "string",
                    "description": "Field for X-axis"
                },
                "y_topic": {
                    "type": "string",
                    "description": "Topic for Y-axis values"
                },
                "y_field": {
                    "type": "string",
                    "description": "Field for Y-axis"
                },
                "window": {
                    "type": "string",
                    "default": "1h"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        x_topic = params["x_topic"]
        y_topic = params["y_topic"]
        window = params.get("window", "1h")
        window_minutes = parse_time_window(window)

        # If same topic, get all messages
        if x_topic == y_topic:
            query = """
            MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
            WHERE t.path = $x_topic
              AND m.timestamp > datetime() - duration({minutes: $window_minutes})
            RETURN m.rawPayload AS payload,
                   m.timestamp AS timestamp,
                   'same' AS source
            ORDER BY m.timestamp ASC
            """
            return query, {"x_topic": x_topic, "window_minutes": window_minutes}
        else:
            # Different topics - need to correlate by time
            query = """
            MATCH (tx:Topic)-[:HAS_MESSAGE]->(mx:Message)
            WHERE tx.path = $x_topic
              AND mx.timestamp > datetime() - duration({minutes: $window_minutes})
            WITH mx
            MATCH (ty:Topic)-[:HAS_MESSAGE]->(my:Message)
            WHERE ty.path = $y_topic
              AND abs(duration.between(mx.timestamp, my.timestamp).seconds) < 60
            RETURN mx.rawPayload AS x_payload,
                   my.rawPayload AS y_payload,
                   mx.timestamp AS timestamp
            ORDER BY mx.timestamp ASC
            LIMIT 500
            """
            return query, {
                "x_topic": x_topic,
                "y_topic": y_topic,
                "window_minutes": window_minutes
            }

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        x_field = params["x_field"]
        y_field = params["y_field"]

        points = []

        for record in data:
            if record.get("source") == "same":
                # Same topic - both fields in one payload
                payload = record.get("payload", {})
                # Parse JSON string payload if needed
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = None

                x_val = None
                y_val = None
                if isinstance(payload, dict):
                    x_val = payload.get(x_field)
                    y_val = payload.get(y_field)
                # Note: raw numeric payload can't be used for same-topic scatter
                # (need two different fields from one payload)

                if x_val is not None and y_val is not None:
                    points.append({"x": x_val, "y": y_val})
            else:
                # Different topics - correlate
                x_payload = record.get("x_payload", {})
                y_payload = record.get("y_payload", {})
                # Parse JSON string payloads if needed
                if isinstance(x_payload, str):
                    try:
                        x_payload = json.loads(x_payload)
                    except (json.JSONDecodeError, TypeError):
                        x_payload = None
                if isinstance(y_payload, str):
                    try:
                        y_payload = json.loads(y_payload)
                    except (json.JSONDecodeError, TypeError):
                        y_payload = None

                # Extract values - handle both dict payloads and raw numeric payloads
                x_val = None
                y_val = None
                if isinstance(x_payload, dict):
                    x_val = x_payload.get(x_field)
                elif isinstance(x_payload, (int, float)):
                    x_val = x_payload  # Raw numeric payload
                if isinstance(y_payload, dict):
                    y_val = y_payload.get(y_field)
                elif isinstance(y_payload, (int, float)):
                    y_val = y_payload  # Raw numeric payload

                if x_val is not None and y_val is not None:
                    points.append({"x": x_val, "y": y_val})

        return {
            "type": "scatter",
            "data": {
                "datasets": [{
                    "label": f"{x_field} vs {y_field}",
                    "data": points,
                    "backgroundColor": get_color(0, 0.6),
                    "borderColor": get_color(0),
                    "pointRadius": 5
                }]
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {
                        "title": {"display": True, "text": x_field},
                        "grace": "10%"
                    },
                    "y": {
                        "title": {"display": True, "text": y_field},
                        "grace": "10%"
                    }
                },
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Correlation: {x_field} vs {y_field}"
                    }
                }
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        topics = [params.get("x_topic"), params.get("y_topic")]
        return [t for t in topics if t]


class HeatmapCorrelationSkill(ChartSkill):
    """Heatmap showing correlation matrix between multiple fields."""

    def __init__(self):
        self.id = "heatmap_correlation"
        self.name = "Correlation Heatmap"
        self.description = "Show correlation strength between multiple variables as a color-coded matrix. Best for understanding relationships across many metrics."
        self.category = "comparison"
        self.chart_type = "matrix"  # Custom type, rendered differently
        self.supports_streaming = False  # Complex calculation, no real-time
        self.parameters_schema = {
            "type": "object",
            "required": ["topics", "fields"],
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "description": "Fields to calculate correlations between"
                },
                "window": {
                    "type": "string",
                    "default": "24h"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        topics = params["topics"]
        window = params.get("window", "24h")
        window_minutes = parse_time_window(window)

        query = """
        MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
        WHERE t.path IN $topics
          AND m.timestamp > datetime() - duration({minutes: $window_minutes})
        RETURN t.path AS topic,
               m.rawPayload AS payload,
               m.timestamp AS timestamp
        ORDER BY m.timestamp ASC
        """

        return query, {"topics": topics, "window_minutes": window_minutes}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        fields = params["fields"]

        # Collect values for each field
        field_values = {f: [] for f in fields}

        for record in data:
            payload = record.get("payload", {})
            # Parse JSON string payload if needed
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = None

            if isinstance(payload, dict):
                for field in fields:
                    if field in payload:
                        field_values[field].append(payload[field])
            elif isinstance(payload, (int, float)):
                # Raw numeric payload - use for "value" field if requested
                if "value" in fields:
                    field_values["value"].append(payload)

        # Calculate correlation matrix
        import math

        def correlation(x_list, y_list):
            if len(x_list) < 2 or len(y_list) < 2:
                return 0
            n = min(len(x_list), len(y_list))
            x = x_list[:n]
            y = y_list[:n]
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            den_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
            den_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
            if den_x == 0 or den_y == 0:
                return 0
            return num / (den_x * den_y)

        matrix = []
        for f1 in fields:
            row = []
            for f2 in fields:
                corr = correlation(field_values[f1], field_values[f2])
                row.append(round(corr, 3))
            matrix.append(row)

        # Return as a custom format (frontend will need to render this specially)
        return {
            "type": "heatmap",
            "data": {
                "labels": fields,
                "matrix": matrix
            },
            "options": {
                "plugins": {
                    "title": {
                        "display": True,
                        "text": "Correlation Matrix"
                    }
                },
                "colorScale": {
                    "min": -1,
                    "max": 1,
                    "colors": ["#ff0000", "#ffffff", "#00ff00"]
                }
            }
        }
