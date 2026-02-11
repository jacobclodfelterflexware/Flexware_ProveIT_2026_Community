"""Project storage service for PLCopen XML projects."""
import os
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Storage directory - can be configured via environment variable
STORAGE_DIR = os.getenv("PLCOPEN_STORAGE_DIR", "/app/data/projects")


class ProjectStore:
    """Simple file-based storage for PLCopen XML projects."""

    def __init__(self):
        self.storage_dir = Path(STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "index.json"
        self._load_index()

    def _load_index(self):
        """Load the project index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    self.index = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load index: {e}")
                self.index = {"projects": []}
        else:
            self.index = {"projects": []}

    def _save_index(self):
        """Save the project index to disk."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise

    def list_projects(self) -> List[dict]:
        """List all stored projects."""
        self._load_index()  # Refresh from disk
        return self.index.get("projects", [])

    def save_project(
        self,
        xml_content: str,
        name: str,
        project_id: Optional[str] = None,
    ) -> dict:
        """
        Save a project to storage.

        Args:
            xml_content: The PLCopen XML content
            name: Project name
            project_id: Optional ID for updating existing project

        Returns:
            Project metadata dict
        """
        self._load_index()

        if project_id is None:
            project_id = str(uuid.uuid4())[:8]

        now = datetime.now().isoformat()

        # Check if project exists
        existing = next(
            (p for p in self.index["projects"] if p["id"] == project_id), None
        )

        if existing:
            # Update existing project
            existing["name"] = name
            existing["updated_at"] = now
            xml_file = self.storage_dir / f"{project_id}.xml"
        else:
            # Create new project entry
            project_meta = {
                "id": project_id,
                "name": name,
                "created_at": now,
                "updated_at": now,
            }
            self.index["projects"].append(project_meta)
            xml_file = self.storage_dir / f"{project_id}.xml"

        # Save XML file
        with open(xml_file, "w", encoding="utf-8") as f:
            f.write(xml_content)

        self._save_index()

        # Return the project metadata
        return next(p for p in self.index["projects"] if p["id"] == project_id)

    def get_project(self, project_id: str) -> Optional[str]:
        """
        Get a project's XML content by ID.

        Args:
            project_id: The project ID

        Returns:
            XML content string or None if not found
        """
        xml_file = self.storage_dir / f"{project_id}.xml"
        if xml_file.exists():
            with open(xml_file, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project by ID.

        Args:
            project_id: The project ID

        Returns:
            True if deleted, False if not found
        """
        self._load_index()

        # Remove from index
        original_len = len(self.index["projects"])
        self.index["projects"] = [
            p for p in self.index["projects"] if p["id"] != project_id
        ]

        if len(self.index["projects"]) == original_len:
            return False

        # Delete XML file
        xml_file = self.storage_dir / f"{project_id}.xml"
        if xml_file.exists():
            xml_file.unlink()

        self._save_index()
        return True


# Singleton instance
_store: Optional[ProjectStore] = None


def get_project_store() -> ProjectStore:
    """Get the project store singleton."""
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store
