"""
Version Tracker Module - Phase 1.7
Tracks corpus versions, generates manifests, and manages rollback tags.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


class VersionTracker:
    """Tracks corpus version history and generates manifests."""

    def __init__(
        self,
        manifest_path: str = "../../data/corpus_version.json",
        history_path: str = "../../data/corpus_version_history.json",
    ):
        self.manifest_path = Path(manifest_path)
        self.history_path = Path(history_path)

    def _load_manifest(self) -> Optional[Dict[str, Any]]:
        """Load current corpus manifest."""
        if not self.manifest_path.exists():
            return None
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load version history."""
        if not self.history_path.exists():
            return []
        with open(self.history_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Save corpus manifest."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def _save_history(self, history: List[Dict[str, Any]]) -> None:
        """Save version history."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def generate_version_tag(self) -> str:
        """Generate a version tag based on current date."""
        now = datetime.now(timezone.utc)
        return f"corpus-v{now.strftime('%Y.%m.1')}"

    def create_manifest(
        self,
        chunks_total: int,
        schemes_count: int,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        embedding_dimensions: int = 384,
        vector_store: str = "ChromaDB",
        collection_name: str = "mf_faq_corpus",
        phases_run: Optional[List[str]] = None,
        source: str = "manual",
        health_report: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new corpus version manifest.

        Args:
            chunks_total: Total number of indexed chunks
            schemes_count: Number of unique schemes
            embedding_model: Name of the embedding model used
            embedding_dimensions: Dimensionality of embeddings
            vector_store: Name of the vector store
            collection_name: ChromaDB collection name
            phases_run: List of phases that were executed
            source: Source of the build (manual, github_actions, etc.)
            health_report: Optional health check report to include

        Returns:
            The generated manifest dictionary
        """
        if phases_run is None:
            phases_run = ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6"]

        manifest = {
            "version": self.generate_version_tag(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "phases_run": phases_run,
            "source": source,
            "chunks_total": chunks_total,
            "schemes_count": schemes_count,
            "embedding_model": embedding_model,
            "embedding_dimensions": embedding_dimensions,
            "vector_store": vector_store,
            "collection_name": collection_name,
        }

        if health_report:
            manifest["health_check"] = {
                "timestamp": health_report.get("timestamp"),
                "overall_passed": health_report.get("overall_passed"),
                "summary": health_report.get("summary"),
            }

        return manifest

    def save_version(
        self,
        manifest: Dict[str, Any],
        append_to_history: bool = True,
    ) -> None:
        """
        Save a new manifest and optionally append to history.

        Args:
            manifest: The manifest dictionary to save
            append_to_history: Whether to append to version history
        """
        self._save_manifest(manifest)

        if append_to_history:
            history = self._load_history()
            history.append({
                "version": manifest["version"],
                "last_updated": manifest["last_updated"],
                "source": manifest["source"],
                "chunks_total": manifest["chunks_total"],
            })
            self._save_history(history)

    def get_current_version(self) -> Optional[Dict[str, Any]]:
        """Get the current corpus version manifest."""
        return self._load_manifest()

    def get_version_history(self) -> List[Dict[str, Any]]:
        """Get the full version history."""
        return self._load_history()

    def get_previous_version(self) -> Optional[Dict[str, Any]]:
        """Get the previous version from history."""
        history = self._load_history()
        if len(history) >= 2:
            return history[-2]
        return None

    def rollback_to_version(self, version_tag: str) -> Optional[Dict[str, Any]]:
        """
        Rollback to a specific version tag.

        Args:
            version_tag: The version tag to rollback to (e.g., "corpus-v2026.05.1")

        Returns:
            The rolled-back manifest, or None if not found
        """
        history = self._load_history()
        for entry in reversed(history):
            if entry.get("version") == version_tag:
                # Create a rollback manifest
                rollback_manifest = dict(entry)
                rollback_manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
                rollback_manifest["source"] = f"rollback_from_{self._load_manifest().get('version', 'unknown')}"
                self._save_manifest(rollback_manifest)
                return rollback_manifest
        return None

    def compare_versions(
        self,
        version_a: Optional[Dict[str, Any]] = None,
        version_b: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Compare two corpus versions and return differences.

        Args:
            version_a: First version (current if None)
            version_b: Second version (previous if None)

        Returns:
            Comparison report
        """
        if version_a is None:
            version_a = self._load_manifest()
        if version_b is None:
            version_b = self.get_previous_version()

        report = {
            "version_a": version_a.get("version") if version_a else None,
            "version_b": version_b.get("version") if version_b else None,
            "differences": {},
            "errors": [],
        }

        if version_a is None or version_b is None:
            report["errors"].append("One or both versions not found")
            return report

        # Compare key metrics
        keys = ["chunks_total", "schemes_count", "embedding_dimensions"]
        for key in keys:
            val_a = version_a.get(key)
            val_b = version_b.get(key)
            if val_a != val_b:
                report["differences"][key] = {
                    "before": val_b,
                    "after": val_a,
                    "delta": val_a - val_b if isinstance(val_a, (int, float)) else None,
                }

        # Compare phases_run
        phases_a = set(version_a.get("phases_run", []))
        phases_b = set(version_b.get("phases_run", []))
        if phases_a != phases_b:
            report["differences"]["phases_run"] = {
                "added": list(phases_a - phases_b),
                "removed": list(phases_b - phases_a),
            }

        # Compare embedding model
        model_a = version_a.get("embedding_model")
        model_b = version_b.get("embedding_model")
        if model_a != model_b:
            report["differences"]["embedding_model"] = {
                "before": model_b,
                "after": model_a,
            }

        report["has_changes"] = len(report["differences"]) > 0
        return report


if __name__ == "__main__":
    # Quick self-test
    vt = VersionTracker()
    manifest = vt.create_manifest(
        chunks_total=416,
        schemes_count=15,
        source="test",
    )
    print(f"Version: {manifest['version']}")
    vt.save_version(manifest)
    print(f"Current: {vt.get_current_version()['version']}")
    print(f"History: {len(vt.get_version_history())} entries")
