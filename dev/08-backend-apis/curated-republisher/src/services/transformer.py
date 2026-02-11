"""Transforms payload keys according to mapping rules."""
import json
import logging
import copy
from typing import Union

logger = logging.getLogger(__name__)


class PayloadTransformer:
    """
    Transforms payload keys according to mapping rules.

    Handles nested JSON structures and arrays.
    """

    def transform(
        self,
        payload: Union[str, bytes, dict],
        payload_mapping: dict[str, str]
    ) -> tuple[dict, str]:
        """
        Transform payload keys according to mapping.

        Args:
            payload: Original payload (string, bytes, or dict)
            payload_mapping: Key mapping {"raw_key": "normalized_key"}

        Returns:
            Tuple of (transformed_dict, transformed_json_string)
        """
        # Parse payload
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")

        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                # Non-JSON payload, return as-is
                return {"value": payload}, json.dumps({"value": payload})
        else:
            data = payload

        if not isinstance(data, dict):
            return {"value": data}, json.dumps({"value": data})

        # Apply transformations
        transformed = self._transform_dict(copy.deepcopy(data), payload_mapping)

        return transformed, json.dumps(transformed)

    def _transform_dict(
        self,
        data: dict,
        mapping: dict[str, str]
    ) -> dict:
        """Recursively transform keys in a dictionary."""
        result = {}

        for key, value in data.items():
            # Check if key should be renamed
            new_key = mapping.get(key, key)

            # Recursively transform nested structures
            if isinstance(value, dict):
                result[new_key] = self._transform_dict(value, mapping)
            elif isinstance(value, list):
                result[new_key] = self._transform_list(value, mapping)
            else:
                result[new_key] = value

        return result

    def _transform_list(
        self,
        data: list,
        mapping: dict[str, str]
    ) -> list:
        """Recursively transform items in a list."""
        result = []
        for item in data:
            if isinstance(item, dict):
                result.append(self._transform_dict(item, mapping))
            elif isinstance(item, list):
                result.append(self._transform_list(item, mapping))
            else:
                result.append(item)
        return result
