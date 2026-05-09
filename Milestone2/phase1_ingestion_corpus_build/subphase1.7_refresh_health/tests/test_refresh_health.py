"""
Tests for Phase 1.7 - Refresh & Health Module
"""

import pytest
import sys
import os
import json
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from health_checker import HealthChecker
from version_tracker import VersionTracker


class TestHealthChecker:
    """Test suite for the HealthChecker class."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        tmpdir = tempfile.mkdtemp(prefix="test_health_")
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()
        indexed_dir = data_dir / "indexed"
        indexed_dir.mkdir()

        yield {
            "root": tmpdir,
            "data": str(data_dir),
            "indexed": str(indexed_dir),
            "manifest": str(data_dir / "corpus_version.json"),
        }
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def fresh_manifest(self, temp_dirs):
        """Create a fresh corpus manifest."""
        manifest = {
            "version": "corpus-v2026.05.1",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "chunks_total": 416,
            "schemes_count": 15,
        }
        with open(temp_dirs["manifest"], "w") as f:
            json.dump(manifest, f)
        return manifest

    @pytest.fixture
    def stale_manifest(self, temp_dirs):
        """Create a stale corpus manifest (31 days old)."""
        from datetime import timedelta
        manifest = {
            "version": "corpus-v2026.04.1",
            "last_updated": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "chunks_total": 400,
            "schemes_count": 15,
        }
        with open(temp_dirs["manifest"], "w") as f:
            json.dump(manifest, f)
        return manifest

    def test_freshness_check_pass(self, temp_dirs, fresh_manifest):
        """Test freshness check passes for recent manifest."""
        hc = HealthChecker(
            corpus_version_path=temp_dirs["manifest"],
            chroma_persist_dir=temp_dirs["indexed"],
        )
        report = hc.check_freshness()
        assert report["passed"] is True
        assert report["age_days"] == 0
        assert len(report["errors"]) == 0

    def test_freshness_check_fail_stale(self, temp_dirs, stale_manifest):
        """Test freshness check fails for stale manifest."""
        hc = HealthChecker(
            corpus_version_path=temp_dirs["manifest"],
            chroma_persist_dir=temp_dirs["indexed"],
            stale_threshold_days=30,
        )
        report = hc.check_freshness()
        assert report["passed"] is False
        assert report["age_days"] == 31
        assert len(report["errors"]) > 0
        assert "stale" in report["errors"][0].lower()

    def test_freshness_check_missing_manifest(self, temp_dirs):
        """Test freshness check with missing manifest."""
        hc = HealthChecker(
            corpus_version_path=str(Path(temp_dirs["data"]) / "missing.json"),
        )
        report = hc.check_freshness()
        assert report["passed"] is False
        assert "not found" in report["errors"][0]

    def test_freshness_check_missing_last_updated(self, temp_dirs):
        """Test freshness check with manifest missing last_updated."""
        manifest = {"version": "v1"}
        with open(temp_dirs["manifest"], "w") as f:
            json.dump(manifest, f)
        hc = HealthChecker(corpus_version_path=temp_dirs["manifest"])
        report = hc.check_freshness()
        assert report["passed"] is False
        assert "last_updated" in report["errors"][0].lower()

    def test_run_all_checks_with_empty_collection(self, temp_dirs, fresh_manifest):
        """Test all checks with empty collection (some should fail)."""
        hc = HealthChecker(
            corpus_version_path=temp_dirs["manifest"],
            chroma_persist_dir=temp_dirs["indexed"],
        )
        report = hc.run_all_checks()
        assert "timestamp" in report
        assert "checks" in report
        assert "summary" in report
        # Freshness should pass, integrity should fail (empty collection)
        assert report["checks"]["freshness"]["passed"] is True
        assert report["checks"]["integrity"]["passed"] is False

    def test_save_report(self, temp_dirs, fresh_manifest):
        """Test saving health report to file."""
        hc = HealthChecker(
            corpus_version_path=temp_dirs["manifest"],
            chroma_persist_dir=temp_dirs["indexed"],
        )
        report = hc.run_all_checks()
        output_path = str(Path(temp_dirs["data"]) / "health_report.json")
        hc.save_report(report, output_path)
        assert Path(output_path).exists()
        with open(output_path, "r") as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == report["timestamp"]


class TestVersionTracker:
    """Test suite for the VersionTracker class."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        tmpdir = tempfile.mkdtemp(prefix="test_version_")
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()
        yield {
            "root": tmpdir,
            "manifest": str(data_dir / "corpus_version.json"),
            "history": str(data_dir / "corpus_version_history.json"),
        }
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_generate_version_tag(self, temp_dirs):
        """Test version tag generation."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )
        tag = vt.generate_version_tag()
        assert tag.startswith("corpus-v")
        # Should contain year and month
        now = datetime.now(timezone.utc)
        assert str(now.year) in tag

    def test_create_manifest(self, temp_dirs):
        """Test manifest creation."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )
        manifest = vt.create_manifest(
            chunks_total=416,
            schemes_count=15,
            source="test",
            phases_run=["1.1", "1.2"],
        )
        assert manifest["chunks_total"] == 416
        assert manifest["schemes_count"] == 15
        assert manifest["source"] == "test"
        assert manifest["phases_run"] == ["1.1", "1.2"]
        assert "version" in manifest
        assert "last_updated" in manifest

    def test_save_and_load_manifest(self, temp_dirs):
        """Test saving and loading manifest."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )
        manifest = vt.create_manifest(chunks_total=100, schemes_count=5, source="test")
        vt.save_version(manifest)

        loaded = vt.get_current_version()
        assert loaded is not None
        assert loaded["version"] == manifest["version"]
        assert loaded["chunks_total"] == 100

    def test_version_history(self, temp_dirs):
        """Test version history tracking."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )

        # Create two versions
        v1 = vt.create_manifest(chunks_total=100, schemes_count=5, source="test1")
        vt.save_version(v1)

        v2 = vt.create_manifest(chunks_total=200, schemes_count=10, source="test2")
        vt.save_version(v2)

        history = vt.get_version_history()
        assert len(history) == 2
        assert history[0]["chunks_total"] == 100
        assert history[1]["chunks_total"] == 200

    def test_get_previous_version(self, temp_dirs):
        """Test getting previous version."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )

        v1 = vt.create_manifest(chunks_total=100, schemes_count=5, source="test1")
        vt.save_version(v1)

        v2 = vt.create_manifest(chunks_total=200, schemes_count=10, source="test2")
        vt.save_version(v2)

        prev = vt.get_previous_version()
        assert prev is not None
        assert prev["chunks_total"] == 100

    def test_rollback_to_version(self, temp_dirs):
        """Test rollback to a specific version."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )

        v1 = vt.create_manifest(chunks_total=100, schemes_count=5, source="test1")
        vt.save_version(v1)

        v2 = vt.create_manifest(chunks_total=200, schemes_count=10, source="test2")
        vt.save_version(v2)

        rolled = vt.rollback_to_version(v1["version"])
        assert rolled is not None
        assert rolled["version"] == v1["version"]
        assert "rollback" in rolled["source"]

        current = vt.get_current_version()
        assert current["version"] == v1["version"]

    def test_rollback_nonexistent_version(self, temp_dirs):
        """Test rollback to non-existent version returns None."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )
        result = vt.rollback_to_version("corpus-v9999.99.99")
        assert result is None

    def test_compare_versions(self, temp_dirs):
        """Test version comparison."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )

        v1 = vt.create_manifest(chunks_total=100, schemes_count=5, source="test1")
        vt.save_version(v1)

        v2 = vt.create_manifest(chunks_total=200, schemes_count=10, source="test2")
        vt.save_version(v2)

        comparison = vt.compare_versions()
        assert comparison["has_changes"] is True
        assert "chunks_total" in comparison["differences"]
        assert comparison["differences"]["chunks_total"]["before"] == 100
        assert comparison["differences"]["chunks_total"]["after"] == 200
        assert comparison["differences"]["chunks_total"]["delta"] == 100

    def test_compare_no_changes(self, temp_dirs):
        """Test version comparison with identical versions."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )

        v1 = vt.create_manifest(chunks_total=100, schemes_count=5, source="test")
        vt.save_version(v1)
        vt.save_version(v1)  # Save same version again

        comparison = vt.compare_versions()
        assert comparison["has_changes"] is False
        assert len(comparison["differences"]) == 0

    def test_manifest_with_health_report(self, temp_dirs):
        """Test manifest creation with embedded health report."""
        vt = VersionTracker(
            manifest_path=temp_dirs["manifest"],
            history_path=temp_dirs["history"],
        )
        health = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_passed": True,
            "summary": {"total_checks": 5, "passed_checks": 5},
        }
        manifest = vt.create_manifest(
            chunks_total=416,
            schemes_count=15,
            health_report=health,
        )
        assert "health_check" in manifest
        assert manifest["health_check"]["overall_passed"] is True
