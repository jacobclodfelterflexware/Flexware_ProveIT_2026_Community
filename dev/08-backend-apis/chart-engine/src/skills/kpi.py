from typing import Optional
from .base import ChartSkill, get_color, parse_time_window


class GaugeSingleSkill(ChartSkill):
    """Single metric gauge showing current value against thresholds."""

    def __init__(self):
        self.id = "gauge_single"
        self.name = "Gauge Chart"
        self.description = "Display a single current value as a gauge with min/max and optional thresholds. Best for showing status metrics like utilization, temperature, or performance scores."
        self.category = "kpi"
        self.chart_type = "doughnut"  # Implemented as half-doughnut
        self.supports_streaming = True
        self.parameters_schema = {
            "type": "object",
            "required": ["topic", "field"],
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to monitor"
                },
                "field": {
                    "type": "string",
                    "description": "Field to display"
                },
                "min": {
                    "type": "number",
                    "default": 0,
                    "description": "Minimum value"
                },
                "max": {
                    "type": "number",
                    "default": 100,
                    "description": "Maximum value"
                },
                "thresholds": {
                    "type": "object",
                    "properties": {
                        "warning": {"type": "number"},
                        "critical": {"type": "number"}
                    },
                    "description": "Optional warning/critical thresholds"
                },
                "unit": {
                    "type": "string",
                    "default": "",
                    "description": "Unit label (e.g., '%', '°C')"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        topic = params["topic"]

        query = """
        MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
        WHERE t.path = $topic
        RETURN m.rawPayload AS payload,
               m.numericValue AS numericValue,
               m.timestamp AS timestamp
        ORDER BY m.timestamp DESC
        LIMIT 1
        """

        return query, {"topic": topic}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        field = params["field"]
        min_val = params.get("min", 0)
        max_val = params.get("max", 100)
        thresholds = params.get("thresholds", {})
        unit = params.get("unit", "")

        # Get current value
        current_value = 0
        if data:
            record = data[0]
            payload = record.get("payload", {})
            if isinstance(payload, dict) and field in payload:
                current_value = payload[field]
            elif record.get("numericValue") is not None:
                current_value = record["numericValue"]

        # Determine color based on thresholds
        color = get_color(2)  # Green by default
        if thresholds:
            if thresholds.get("critical") and current_value >= thresholds["critical"]:
                color = "rgb(255, 99, 132)"  # Red
            elif thresholds.get("warning") and current_value >= thresholds["warning"]:
                color = "rgb(255, 206, 86)"  # Yellow

        # Calculate gauge percentage
        range_val = max_val - min_val
        percentage = ((current_value - min_val) / range_val * 100) if range_val > 0 else 0
        percentage = max(0, min(100, percentage))

        return {
            "type": "gauge",
            "data": {
                "value": current_value,
                "percentage": percentage,
                "min": min_val,
                "max": max_val,
                "unit": unit,
                "color": color
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": field
                    }
                },
                "thresholds": thresholds
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        return [params.get("topic")] if params.get("topic") else []

    def transform_message(self, topic: str, payload: dict, params: dict) -> Optional[dict]:
        field = params.get("field")
        if field and field in payload:
            return {
                "value": payload[field],
                "timestamp": payload.get("timestamp")
            }
        return None


class KPICardSkill(ChartSkill):
    """KPI card showing current value with trend indicator."""

    def __init__(self):
        self.id = "kpi_card"
        self.name = "KPI Card"
        self.description = "Display a key metric with its current value and trend compared to a previous period. Best for dashboards showing important business metrics."
        self.category = "kpi"
        self.chart_type = "kpi"  # Custom type
        self.supports_streaming = True
        self.parameters_schema = {
            "type": "object",
            "required": ["topic", "field"],
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to monitor"
                },
                "field": {
                    "type": "string",
                    "description": "Field to display"
                },
                "comparison_window": {
                    "type": "string",
                    "default": "1h",
                    "description": "Time window for comparison (e.g., '1h', '24h')"
                },
                "unit": {
                    "type": "string",
                    "default": ""
                },
                "format": {
                    "type": "string",
                    "enum": ["number", "percentage", "currency"],
                    "default": "number"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        topic = params["topic"]
        window = params.get("comparison_window", "1h")
        window_minutes = parse_time_window(window)

        query = """
        MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
        WHERE t.path = $topic
        WITH m
        ORDER BY m.timestamp DESC
        WITH collect(m) AS messages
        WITH messages[0] AS current,
             [m IN messages WHERE m.timestamp < datetime() - duration({minutes: $half_window})][0] AS previous
        RETURN current.rawPayload AS current_payload,
               current.numericValue AS current_numeric,
               current.timestamp AS current_timestamp,
               previous.rawPayload AS previous_payload,
               previous.numericValue AS previous_numeric
        """

        return query, {"topic": topic, "half_window": window_minutes // 2}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        field = params["field"]
        unit = params.get("unit", "")
        format_type = params.get("format", "number")

        current_value = 0
        previous_value = None
        trend = None
        trend_percentage = None

        if data:
            record = data[0]

            # Current value
            current_payload = record.get("current_payload", {})
            if isinstance(current_payload, dict) and field in current_payload:
                current_value = current_payload[field]
            elif record.get("current_numeric") is not None:
                current_value = record["current_numeric"]

            # Previous value for trend
            previous_payload = record.get("previous_payload", {})
            if isinstance(previous_payload, dict) and field in previous_payload:
                previous_value = previous_payload[field]
            elif record.get("previous_numeric") is not None:
                previous_value = record["previous_numeric"]

            # Calculate trend
            if previous_value is not None and previous_value != 0:
                trend_percentage = ((current_value - previous_value) / abs(previous_value)) * 100
                trend = "up" if trend_percentage > 0 else "down" if trend_percentage < 0 else "flat"

        return {
            "type": "kpi",
            "data": {
                "value": current_value,
                "previous_value": previous_value,
                "trend": trend,
                "trend_percentage": round(trend_percentage, 1) if trend_percentage else None,
                "unit": unit,
                "format": format_type
            },
            "options": {
                "plugins": {
                    "title": {
                        "display": True,
                        "text": field
                    }
                }
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        return [params.get("topic")] if params.get("topic") else []


class SparklineGridSkill(ChartSkill):
    """Grid of sparkline mini-charts for multiple topics."""

    def __init__(self):
        self.id = "sparkline_grid"
        self.name = "Sparkline Grid"
        self.description = "Display multiple mini line charts in a grid layout. Best for monitoring many metrics at once in a compact dashboard view."
        self.category = "kpi"
        self.chart_type = "sparkline_grid"  # Custom type
        self.supports_streaming = True
        self.parameters_schema = {
            "type": "object",
            "required": ["topics", "field"],
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Topics to display as sparklines"
                },
                "field": {
                    "type": "string",
                    "description": "Field to chart"
                },
                "columns": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 6,
                    "description": "Number of columns in grid"
                },
                "window": {
                    "type": "string",
                    "default": "1h"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        topics = params["topics"]
        window = params.get("window", "1h")
        window_minutes = parse_time_window(window)

        query = """
        MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
        WHERE t.path IN $topics
          AND m.timestamp > datetime() - duration({minutes: $window_minutes})
        RETURN t.path AS topic,
               m.rawPayload AS payload,
               m.numericValue AS numericValue,
               m.timestamp AS timestamp
        ORDER BY t.path, m.timestamp ASC
        """

        return query, {"topics": topics, "window_minutes": window_minutes}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        field = params["field"]
        columns = params.get("columns", 3)

        # Group by topic
        topic_data = {}
        for record in data:
            topic = record.get("topic", "")
            if topic not in topic_data:
                topic_data[topic] = []

            payload = record.get("payload", {})
            if isinstance(payload, dict) and field in payload:
                topic_data[topic].append(payload[field])
            elif record.get("numericValue") is not None:
                topic_data[topic].append(record["numericValue"])

        # Build sparklines
        sparklines = []
        for topic, values in topic_data.items():
            short_name = topic.split("/")[-1] if "/" in topic else topic
            current = values[-1] if values else 0
            sparklines.append({
                "topic": topic,
                "label": short_name,
                "data": values[-30:],  # Last 30 points
                "current": current,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0
            })

        return {
            "type": "sparkline_grid",
            "data": {
                "sparklines": sparklines,
                "columns": columns
            },
            "options": {
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Sparklines: {field}"
                    }
                }
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        return params.get("topics", [])
