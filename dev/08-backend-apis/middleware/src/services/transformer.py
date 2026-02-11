"""JSON message transformer for key renaming."""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessageTransformer:
    """Transforms JSON messages by renaming keys."""

    def transform(
        self,
        payload: Dict[str, Any],
        transformations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Apply key transformations to a payload.

        Args:
            payload: The original JSON payload
            transformations: List of transformation configs, each with:
                - source_key: Original key name
                - target_key: New key name
                - json_path: Optional path for nested keys (e.g., "data.sensors")

        Returns:
            Transformed payload with renamed keys
        """
        if not transformations:
            return payload

        # Sort by transform_order
        sorted_transforms = sorted(
            transformations,
            key=lambda t: t.get("transform_order", 0),
        )

        result = self._deep_copy(payload)

        for transform in sorted_transforms:
            if not transform.get("is_active", True):
                continue

            source_key = transform.get("source_key")
            target_key = transform.get("target_key")
            json_path = transform.get("json_path")

            if not source_key or not target_key:
                continue

            if json_path:
                # Apply to nested path
                result = self._transform_at_path(
                    result, json_path, source_key, target_key
                )
            else:
                # Apply at root level and recursively
                result = self._transform_recursive(result, source_key, target_key)

        return result

    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of the object."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj

    def _transform_recursive(
        self,
        obj: Any,
        source_key: str,
        target_key: str,
    ) -> Any:
        """Recursively transform keys throughout the object."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                new_key = target_key if key == source_key else key
                result[new_key] = self._transform_recursive(value, source_key, target_key)
            return result
        elif isinstance(obj, list):
            return [
                self._transform_recursive(item, source_key, target_key)
                for item in obj
            ]
        else:
            return obj

    def _transform_at_path(
        self,
        obj: Dict[str, Any],
        json_path: str,
        source_key: str,
        target_key: str,
    ) -> Dict[str, Any]:
        """
        Transform a key at a specific JSON path.

        Supports paths like:
        - "data.sensors" -> nested object
        - "data.sensors[*]" -> all array elements
        - "data.sensors[0]" -> specific array index
        """
        parts = self._parse_path(json_path)
        return self._apply_at_path(obj, parts, source_key, target_key)

    def _parse_path(self, path: str) -> List[str]:
        """Parse a JSON path into parts."""
        # Handle array notation
        parts = []
        for part in path.split("."):
            # Check for array notation
            match = re.match(r"(\w+)\[(\d+|\*)\]", part)
            if match:
                parts.append(match.group(1))
                parts.append(f"[{match.group(2)}]")
            else:
                parts.append(part)
        return parts

    def _apply_at_path(
        self,
        obj: Any,
        path_parts: List[str],
        source_key: str,
        target_key: str,
    ) -> Any:
        """Apply transformation at specified path."""
        if not path_parts:
            # At target location, transform the key
            if isinstance(obj, dict):
                return self._rename_key(obj, source_key, target_key)
            elif isinstance(obj, list):
                return [
                    self._rename_key(item, source_key, target_key)
                    if isinstance(item, dict)
                    else item
                    for item in obj
                ]
            return obj

        part = path_parts[0]
        remaining = path_parts[1:]

        if isinstance(obj, dict):
            if part.startswith("["):
                # This shouldn't happen at dict level
                return obj

            if part in obj:
                result = dict(obj)
                result[part] = self._apply_at_path(obj[part], remaining, source_key, target_key)
                return result

        elif isinstance(obj, list):
            if part == "[*]":
                # Apply to all elements
                return [
                    self._apply_at_path(item, remaining, source_key, target_key)
                    for item in obj
                ]
            elif part.startswith("[") and part.endswith("]"):
                # Specific index
                try:
                    idx = int(part[1:-1])
                    if 0 <= idx < len(obj):
                        result = list(obj)
                        result[idx] = self._apply_at_path(
                            obj[idx], remaining, source_key, target_key
                        )
                        return result
                except ValueError:
                    pass

        return obj

    def _rename_key(
        self,
        obj: Dict[str, Any],
        source_key: str,
        target_key: str,
    ) -> Dict[str, Any]:
        """Rename a key in a dictionary."""
        if source_key not in obj:
            return obj

        result = {}
        for key, value in obj.items():
            new_key = target_key if key == source_key else key
            result[new_key] = value
        return result
