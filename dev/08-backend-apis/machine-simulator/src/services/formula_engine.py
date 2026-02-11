"""Safe formula evaluation engine using simpleeval."""

import logging
import math
import random
import time
from typing import Any, Optional

from simpleeval import SimpleEval, EvalWithCompoundTypes

logger = logging.getLogger(__name__)


class FormulaEngine:
    """Safe mathematical expression evaluator for generating simulated values."""

    def __init__(self):
        # Create evaluator with safe functions and operators
        self.evaluator = EvalWithCompoundTypes()

        # Add safe math functions
        self.evaluator.functions = {
            # Trigonometric
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            # Math operations
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
            "floor": math.floor,
            "ceil": math.ceil,
            "sqrt": math.sqrt,
            "pow": pow,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            # Random
            "random": random.random,
            "randint": random.randint,
            # Type conversions
            "int": int,
            "float": float,
            # Time
            "now": lambda: time.time(),  # Returns current Unix timestamp
        }

        # Add math constants
        self.evaluator.names = {
            "pi": math.pi,
            "e": math.e,
        }

    def evaluate(
        self,
        formula: str,
        t: Optional[float] = None,
        i: int = 0,
        extra_vars: Optional[dict] = None
    ) -> Any:
        """
        Evaluate a formula with the given variables.

        Args:
            formula: Mathematical expression to evaluate
            t: Unix timestamp in seconds (defaults to current time)
            i: Iteration count
            extra_vars: Additional variables to make available

        Returns:
            The evaluated result

        Raises:
            ValueError: If the formula is invalid or evaluation fails
        """
        if t is None:
            t = time.time()

        # Set up variables - spread old names first so new t/i override them
        variables = {
            **self.evaluator.names,
            "t": t,
            "i": i,
        }

        if extra_vars:
            variables.update(extra_vars)

        self.evaluator.names = variables

        try:
            result = self.evaluator.eval(formula)
            return result
        except Exception as e:
            logger.error(f"Formula evaluation error: {e} (formula: {formula})")
            raise ValueError(f"Invalid formula '{formula}': {e}")

    def validate(self, formula: str) -> tuple[bool, Optional[str]]:
        """
        Validate a formula without evaluating it with real data.

        Args:
            formula: The formula to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Test with dummy values
            self.evaluate(formula, t=0, i=0)
            return True, None
        except Exception as e:
            return False, str(e)

    def generate_value(
        self,
        field_type: str,
        formula: Optional[str] = None,
        static_value: Any = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        t: Optional[float] = None,
        i: int = 0
    ) -> Any:
        """
        Generate a value for a field based on its definition.

        Args:
            field_type: Type of field (number, integer, boolean, string)
            formula: Formula to evaluate (for dynamic fields)
            static_value: Static value to return (for constant fields)
            min_value: Minimum bound for numeric values
            max_value: Maximum bound for numeric values
            t: Unix timestamp
            i: Iteration count

        Returns:
            Generated value of appropriate type
        """
        # Static value takes precedence
        if static_value is not None:
            return static_value

        # If no formula, generate default value based on type
        if not formula:
            if field_type == "boolean":
                return random.choice([True, False])
            elif field_type == "string":
                return f"value_{i}"
            elif field_type == "integer":
                low = int(min_value) if min_value is not None else 0
                high = int(max_value) if max_value is not None else 100
                return random.randint(low, high)
            elif field_type == "number":
                low = min_value if min_value is not None else 0.0
                high = max_value if max_value is not None else 100.0
                return random.uniform(low, high)
            return None

        # Evaluate formula
        value = self.evaluate(formula, t=t, i=i)

        # Apply type conversion
        if field_type == "integer":
            value = int(round(value))
        elif field_type == "number":
            value = float(value)
        elif field_type == "boolean":
            value = bool(value)
        elif field_type == "string":
            value = str(value)

        # Apply bounds for numeric types
        if field_type in ("integer", "number"):
            if min_value is not None:
                value = max(value, min_value if field_type == "number" else int(min_value))
            if max_value is not None:
                value = min(value, max_value if field_type == "number" else int(max_value))

        return value


# Singleton instance
formula_engine = FormulaEngine()
