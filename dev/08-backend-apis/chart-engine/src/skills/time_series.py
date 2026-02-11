import json
from typing import Optional
from .base import ChartSkill, ChartResult, get_color, parse_time_window


class TimeSeriesLineSkill(ChartSkill):
    """Multi-line chart showing values over time."""

    def __init__(self):
        self.id = "time_series_line"
        self.name = "Time Series Line Chart"
        self.description = "Display one or more metrics as lines over time. Best for showing trends, patterns, and changes in values."
        self.category = "time_series"
        self.chart_type = "line"
        self.supports_streaming = True
        self.parameters_schema = {
            "type": "object",
            "required": ["topics", "fields"],
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "List of topic paths to chart"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Fields to extract from payloads (e.g., ['value', 'temperature'])"
                },
                "window": {
                    "type": "string",
                    "default": "1h",
                    "description": "Time window (e.g., '30m', '1h', '24h', '7d')"
                },
                "aggregation": {
                    "type": "string",
                    "enum": ["none", "avg", "min", "max", "sum"],
                    "default": "none",
                    "description": "Aggregation method for data points"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        topics = params["topics"]
        fields = params["fields"]
        window = params.get("window", "1h")
        window_minutes = parse_time_window(window)

        query = """
        MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
        WHERE t.path IN $topics
          AND m.timestamp > datetime() - duration({minutes: $window_minutes})
        RETURN t.path AS topic,
               m.rawPayload AS payload,
               m.timestamp AS timestamp,
               m.numericValue AS numericValue
        ORDER BY m.timestamp ASC
        """

        return query, {
            "topics": topics,
            "window_minutes": window_minutes
        }

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        fields = params["fields"]
        topics = params["topics"]

        # Group data by topic and field
        datasets = {}
        labels = set()

        for record in data:
            topic = record.get("topic", "")
            timestamp = record.get("timestamp")
            payload = record.get("payload", {})
            numeric_value = record.get("numericValue")

            # Parse JSON string payload if needed
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}

            if timestamp:
                labels.add(timestamp.isoformat())

            for field in fields:
                series_key = f"{topic}:{field}" if len(topics) > 1 else field

                if series_key not in datasets:
                    datasets[series_key] = {
                        "label": series_key,
                        "data": [],
                        "borderColor": get_color(len(datasets)),
                        "backgroundColor": get_color(len(datasets), 0.1),
                        "fill": False,
                        "tension": 0.1
                    }

                # Extract value
                if isinstance(payload, dict) and field in payload:
                    value = payload[field]
                elif field == "value" and numeric_value is not None:
                    value = numeric_value
                else:
                    continue

                if timestamp:
                    datasets[series_key]["data"].append({
                        "x": timestamp.isoformat(),
                        "y": value
                    })

        sorted_labels = sorted(labels)

        return {
            "type": "line",
            "data": {
                "labels": sorted_labels,
                "datasets": list(datasets.values())
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {
                        "type": "time",
                        "time": {
                            "unit": "minute"
                        },
                        "title": {
                            "display": True,
                            "text": "Time"
                        }
                    },
                    "y": {
                        "title": {
                            "display": True,
                            "text": "Value"
                        },
                        "grace": "10%"
                    }
                },
                "plugins": {
                    "legend": {
                        "position": "top"
                    },
                    "title": {
                        "display": True,
                        "text": f"Time Series: {', '.join(fields)}"
                    }
                }
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        return params.get("topics", [])

    def transform_message(self, topic: str, payload: dict, params: dict) -> Optional[dict]:
        fields = params.get("fields", ["value"])
        results = []

        for field in fields:
            if field in payload:
                results.append({
                    "x": payload.get("timestamp", "now"),
                    "y": payload[field],
                    "series": f"{topic}:{field}"
                })

        return results[0] if len(results) == 1 else results if results else None


class TimeSeriesAreaSkill(ChartSkill):
    """Stacked area chart for showing cumulative values over time."""

    def __init__(self):
        self.id = "time_series_area"
        self.name = "Time Series Area Chart"
        self.description = "Display values as stacked or overlapping areas. Best for showing proportions and cumulative totals over time."
        self.category = "time_series"
        self.chart_type = "line"
        self.supports_streaming = True
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
                    "minItems": 1
                },
                "window": {
                    "type": "string",
                    "default": "1h"
                },
                "stacked": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to stack the areas"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        # Same query as line chart
        topics = params["topics"]
        window = params.get("window", "1h")
        window_minutes = parse_time_window(window)

        query = """
        MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
        WHERE t.path IN $topics
          AND m.timestamp > datetime() - duration({minutes: $window_minutes})
        RETURN t.path AS topic,
               m.rawPayload AS payload,
               m.timestamp AS timestamp,
               m.numericValue AS numericValue
        ORDER BY m.timestamp ASC
        """

        return query, {"topics": topics, "window_minutes": window_minutes}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        fields = params["fields"]
        stacked = params.get("stacked", True)

        datasets = {}
        labels = set()

        for record in data:
            topic = record.get("topic", "")
            timestamp = record.get("timestamp")
            payload = record.get("payload", {})

            # Parse JSON string payload if needed
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}

            if timestamp:
                labels.add(timestamp.isoformat())

            for field in fields:
                series_key = f"{topic}:{field}"

                if series_key not in datasets:
                    color_idx = len(datasets)
                    datasets[series_key] = {
                        "label": series_key,
                        "data": [],
                        "borderColor": get_color(color_idx),
                        "backgroundColor": get_color(color_idx, 0.5),
                        "fill": True,
                        "tension": 0.3
                    }

                if isinstance(payload, dict) and field in payload and timestamp:
                    datasets[series_key]["data"].append({
                        "x": timestamp.isoformat(),
                        "y": payload[field]
                    })

        return {
            "type": "line",
            "data": {
                "labels": sorted(labels),
                "datasets": list(datasets.values())
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {"type": "time", "stacked": stacked},
                    "y": {"stacked": stacked, "grace": "10%"}
                },
                "plugins": {
                    "filler": {"propagate": False},
                    "title": {
                        "display": True,
                        "text": f"Area Chart: {', '.join(fields)}"
                    }
                }
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        return params.get("topics", [])


class TimeSeriesMultiAxisSkill(ChartSkill):
    """Dual Y-axis chart for comparing metrics with different scales."""

    def __init__(self):
        self.id = "time_series_multi_axis"
        self.name = "Dual Y-Axis Chart"
        self.description = "Display two metrics with different scales on separate Y axes. Best for comparing metrics that have different units or ranges."
        self.category = "time_series"
        self.chart_type = "line"
        self.supports_streaming = True
        self.parameters_schema = {
            "type": "object",
            "required": ["left_topics", "left_field", "right_topics", "right_field"],
            "properties": {
                "left_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Topics for left Y-axis"
                },
                "left_field": {
                    "type": "string",
                    "description": "Field for left Y-axis"
                },
                "right_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Topics for right Y-axis"
                },
                "right_field": {
                    "type": "string",
                    "description": "Field for right Y-axis"
                },
                "window": {
                    "type": "string",
                    "default": "1h"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        all_topics = params["left_topics"] + params["right_topics"]
        window = params.get("window", "1h")
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

        return query, {"topics": all_topics, "window_minutes": window_minutes}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        left_topics = set(params["left_topics"])
        right_topics = set(params["right_topics"])
        left_field = params["left_field"]
        right_field = params["right_field"]

        left_data = []
        right_data = []
        labels = set()

        for record in data:
            topic = record.get("topic", "")
            timestamp = record.get("timestamp")
            payload = record.get("payload", {})

            # Parse JSON string payload if needed
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}

            if timestamp:
                labels.add(timestamp.isoformat())

            if timestamp and topic in left_topics and isinstance(payload, dict) and left_field in payload:
                left_data.append({"x": timestamp.isoformat(), "y": payload[left_field]})

            if timestamp and topic in right_topics and isinstance(payload, dict) and right_field in payload:
                right_data.append({"x": timestamp.isoformat(), "y": payload[right_field]})

        return {
            "type": "line",
            "data": {
                "labels": sorted(labels),
                "datasets": [
                    {
                        "label": left_field,
                        "data": left_data,
                        "borderColor": get_color(0),
                        "backgroundColor": get_color(0, 0.1),
                        "yAxisID": "y"
                    },
                    {
                        "label": right_field,
                        "data": right_data,
                        "borderColor": get_color(1),
                        "backgroundColor": get_color(1, 0.1),
                        "yAxisID": "y1"
                    }
                ]
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {"type": "time"},
                    "y": {
                        "type": "linear",
                        "position": "left",
                        "title": {"display": True, "text": left_field},
                        "grace": "10%"
                    },
                    "y1": {
                        "type": "linear",
                        "position": "right",
                        "title": {"display": True, "text": right_field},
                        "grid": {"drawOnChartArea": False},
                        "grace": "10%"
                    }
                }
            }
        }

    def build_subscriptions(self, params: dict) -> list[str]:
        return params.get("left_topics", []) + params.get("right_topics", [])
