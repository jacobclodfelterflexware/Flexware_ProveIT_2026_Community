import os
import yaml
import logging
from pathlib import Path
from typing import Optional

from .base import ChartSkill
from .time_series import TimeSeriesLineSkill, TimeSeriesAreaSkill, TimeSeriesMultiAxisSkill
from .comparison import BarComparisonSkill, ScatterCorrelationSkill, HeatmapCorrelationSkill
from .distribution import HistogramSkill
from .kpi import GaugeSingleSkill, KPICardSkill, SparklineGridSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry of available chart skills.
    Loads skill definitions and provides lookup functionality.
    """

    def __init__(self):
        self.skills: dict[str, ChartSkill] = {}

    def load_skills(self):
        """Load all built-in skills."""
        # Register built-in skill classes
        built_in_skills = [
            # Time Series
            TimeSeriesLineSkill(),
            TimeSeriesAreaSkill(),
            TimeSeriesMultiAxisSkill(),
            # Comparison
            BarComparisonSkill(),
            ScatterCorrelationSkill(),
            HeatmapCorrelationSkill(),
            # Distribution
            HistogramSkill(),
            # KPI
            GaugeSingleSkill(),
            KPICardSkill(),
            SparklineGridSkill(),
        ]

        for skill in built_in_skills:
            self.register_skill(skill)

        logger.info(f"Loaded {len(self.skills)} skills")

    def register_skill(self, skill: ChartSkill):
        """Register a skill in the registry."""
        self.skills[skill.id] = skill
        logger.debug(f"Registered skill: {skill.id}")

    def get_skill(self, skill_id: str) -> Optional[ChartSkill]:
        """Get a skill by ID."""
        return self.skills.get(skill_id)

    def get_skill_summaries(self) -> list[dict]:
        """Get summaries of all skills for LLM context."""
        return [skill.get_summary() for skill in self.skills.values()]

    def list_skills_by_category(self) -> dict[str, list[str]]:
        """Group skills by category."""
        categories = {}
        for skill in self.skills.values():
            if skill.category not in categories:
                categories[skill.category] = []
            categories[skill.category].append(skill.id)
        return categories
