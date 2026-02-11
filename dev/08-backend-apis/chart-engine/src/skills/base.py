from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import json


@dataclass
class ChartResult:
    """Result from skill execution."""
    chart_config: dict  # Chart.js compatible config
    initial_data: dict  # Initial data points
    subscriptions: list[str] = field(default_factory=list)  # Topics to subscribe for streaming


@dataclass
class ChartSkill(ABC):
    """
    Base class for chart skills.

    Each skill defines:
    - What parameters it accepts (JSON Schema)
    - How to query data (Cypher template)
    - How to format the chart (Chart.js config)
    - How to handle real-time updates
    """
    id: str
    name: str
    description: str
    category: str  # "time_series", "comparison", "distribution", "kpi", "regression"

    # JSON Schema for parameter validation
    parameters_schema: dict

    # Chart output configuration
    chart_type: str  # "line", "bar", "scatter", "pie", "doughnut", "gauge", etc.

    # Real-time support
    supports_streaming: bool = True

    @abstractmethod
    def build_cypher_query(self, params: dict) -> tuple[str, dict]:
        """
        Build the Cypher query for this skill.

        Args:
            params: Validated parameters

        Returns:
            Tuple of (query_string, query_parameters)
        """
        pass

    @abstractmethod
    def build_chart_config(self, data: list[dict], params: dict) -> dict:
        """
        Build Chart.js configuration from query results.

        Args:
            data: Query results
            params: Skill parameters

        Returns:
            Chart.js compatible configuration
        """
        pass

    def build_subscriptions(self, params: dict) -> list[str]:
        """
        Build list of topic paths to subscribe to for real-time updates.
        Override in subclasses that support streaming.
        """
        return params.get("topics", [])

    def transform_message(self, topic: str, payload: dict, params: dict) -> Optional[dict]:
        """
        Transform an incoming MQTT message to a chart data point.
        Override in subclasses that support streaming.

        Returns:
            Dict with x, y, series keys or None to skip
        """
        return None

    def get_summary(self) -> dict:
        """Get a summary for LLM context."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "chart_type": self.chart_type,
            "parameters_schema": self.parameters_schema,
            "supports_streaming": self.supports_streaming
        }


# Color palette for charts
CHART_COLORS = [
    "rgb(75, 192, 192)",    # Teal
    "rgb(255, 99, 132)",    # Red
    "rgb(54, 162, 235)",    # Blue
    "rgb(255, 206, 86)",    # Yellow
    "rgb(153, 102, 255)",   # Purple
    "rgb(255, 159, 64)",    # Orange
    "rgb(199, 199, 199)",   # Gray
    "rgb(83, 102, 255)",    # Indigo
    "rgb(255, 99, 255)",    # Pink
    "rgb(99, 255, 132)",    # Green
]


def get_color(index: int, alpha: float = 1.0) -> str:
    """Get a color from the palette with optional alpha."""
    color = CHART_COLORS[index % len(CHART_COLORS)]
    if alpha < 1.0:
        # Convert rgb to rgba
        return color.replace("rgb(", "rgba(").replace(")", f", {alpha})")
    return color


def parse_time_window(window: str) -> int:
    """Parse time window string to minutes."""
    window = window.lower().strip()
    if window.endswith("m"):
        return int(window[:-1])
    elif window.endswith("h"):
        return int(window[:-1]) * 60
    elif window.endswith("d"):
        return int(window[:-1]) * 60 * 24
    elif window.endswith("w"):
        return int(window[:-1]) * 60 * 24 * 7
    else:
        # Default to 1 hour
        return 60
