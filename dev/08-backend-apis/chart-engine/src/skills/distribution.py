from typing import Optional
from .base import ChartSkill, get_color, parse_time_window
import math


class HistogramSkill(ChartSkill):
    """Histogram showing value distribution."""

    def __init__(self):
        self.id = "histogram"
        self.name = "Histogram"
        self.description = "Show distribution of values as frequency bars in bins. Best for understanding the spread and shape of data."
        self.category = "distribution"
        self.chart_type = "bar"
        self.supports_streaming = False  # Need full dataset for binning
        self.parameters_schema = {
            "type": "object",
            "required": ["topic", "field"],
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to analyze"
                },
                "field": {
                    "type": "string",
                    "description": "Field to create histogram for"
                },
                "bins": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 2,
                    "maximum": 50,
                    "description": "Number of bins"
                },
                "window": {
                    "type": "string",
                    "default": "24h"
                }
            }
        }

    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        topic = params["topic"]
        window = params.get("window", "24h")
        window_minutes = parse_time_window(window)

        query = """
        MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
        WHERE t.path = $topic
          AND m.timestamp > datetime() - duration({minutes: $window_minutes})
        RETURN m.rawPayload AS payload,
               m.numericValue AS numericValue
        """

        return query, {"topic": topic, "window_minutes": window_minutes}

    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        field = params["field"]
        num_bins = params.get("bins", 10)

        # Extract values
        values = []
        for record in data:
            payload = record.get("payload", {})
            if isinstance(payload, dict) and field in payload:
                try:
                    values.append(float(payload[field]))
                except (ValueError, TypeError):
                    pass
            elif record.get("numericValue") is not None:
                values.append(float(record["numericValue"]))

        if not values:
            return {
                "type": "bar",
                "data": {"labels": [], "datasets": []},
                "options": {"plugins": {"title": {"display": True, "text": "No data"}}}
            }

        # Calculate histogram
        min_val = min(values)
        max_val = max(values)
        bin_width = (max_val - min_val) / num_bins if max_val != min_val else 1

        bins = [0] * num_bins
        bin_labels = []

        for i in range(num_bins):
            bin_start = min_val + i * bin_width
            bin_end = bin_start + bin_width
            bin_labels.append(f"{bin_start:.1f}-{bin_end:.1f}")

        for v in values:
            bin_idx = int((v - min_val) / bin_width)
            if bin_idx >= num_bins:
                bin_idx = num_bins - 1
            bins[bin_idx] += 1

        return {
            "type": "bar",
            "data": {
                "labels": bin_labels,
                "datasets": [{
                    "label": f"Frequency of {field}",
                    "data": bins,
                    "backgroundColor": get_color(0, 0.7),
                    "borderColor": get_color(0),
                    "borderWidth": 1
                }]
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Distribution of {field}"
                    },
                    "legend": {
                        "display": False
                    }
                },
                "scales": {
                    "x": {
                        "title": {"display": True, "text": field}
                    },
                    "y": {
                        "title": {"display": True, "text": "Frequency"},
                        "beginAtZero": True
                    }
                }
            }
        }
