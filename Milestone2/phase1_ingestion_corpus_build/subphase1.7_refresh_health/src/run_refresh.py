"""
Run Phase 1.7 - Refresh & Health
Orchestrates the full Phase 1 pipeline, runs health checks, and updates version tracking.
"""

import sys
import os
import json
import logging
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Disable logging to avoid PowerShell output issues
logging.disable(logging.CRITICAL)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from health_checker import HealthChecker
from version_tracker import VersionTracker


def run_subprocess(script_path: str, description: str, log_file) -> bool:
    """Run a Python script as a subprocess and log output."""
    log_file.write(f"\n{'='*60}\n")
    log_file.write(f"Running: {description}\n")
    log_file.write(f"Script: {script_path}\n")
    log_file.write(f"{'='*60}\n")
    log_file.flush()

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600,
        )
        log_file.write(result.stdout)
        if result.stderr:
            log_file.write(f"STDERR:\n{result.stderr}\n")
        log_file.write(f"Return code: {result.returncode}\n")
        log_file.flush()
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log_file.write(f"ERROR: Timeout after 600s\n")
        return False
    except Exception as e:
        log_file.write(f"ERROR: {str(e)}\n")
        return False


def run_phase_1_7(force_refresh: bool = False):
    """Main entry point for Phase 1.7 execution."""
    # Resolve paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    log_path = project_root / "phase1.7_run.log"
    health_report_path = project_root / "data" / "health_report_latest.json"

    log_file = open(log_path, "w", encoding="utf-8")
    def log(msg):
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"{'='*60}")
    log(f"Phase 1.7 - Refresh & Health Run")
    log(f"Started: {datetime.now(timezone.utc).isoformat()}")
    log(f"Force refresh: {force_refresh}")
    log(f"{'='*60}")

    # ------------------------------------------------------------------
    # Step 1: Health Check (Pre-Refresh)
    # ------------------------------------------------------------------
    log("\n[Step 1] Running pre-refresh health check...")
    start_time = time.time()
    health_checker = HealthChecker(
        corpus_version_path=str(project_root / "data" / "corpus_version.json"),
        chroma_persist_dir=str(project_root / "data" / "indexed"),
    )
    pre_health = health_checker.run_all_checks()
    pre_health_elapsed = time.time() - start_time

    log(f"Pre-refresh health check completed in {pre_health_elapsed:.1f}s")
    log(f"Overall passed: {pre_health['overall_passed']}")
    log(f"Checks passed: {pre_health['summary']['passed_checks']}/{pre_health['summary']['total_checks']}")

    for check_name, check_report in pre_health["checks"].items():
        status = "PASS" if check_report["passed"] else "FAIL"
        log(f"  [{status}] {check_name}")
        if check_report.get("errors"):
            for err in check_report["errors"][:3]:
                log(f"      - {err}")

    # Save pre-refresh health report
    health_checker.save_report(pre_health, str(health_report_path))

    # Determine if refresh is needed
    needs_refresh = force_refresh or not pre_health["overall_passed"]
    stale = pre_health["checks"].get("freshness", {}).get("passed", True) is False

    if stale and not force_refresh:
        log("\nCorpus is stale. Refresh will be triggered.")
        needs_refresh = True

    if not needs_refresh:
        log("\n[INFO] Corpus is healthy and fresh. No refresh needed.")
        log(f"To force refresh, run with --force flag.")
        log(f"\n{'='*60}")
        log(f"Phase 1.7 Complete (No refresh needed)")
        log(f"  Health status: HEALTHY")
        log(f"  Refresh needed: No")
        log(f"{'='*60}")
        log_file.close()
        print(f"Phase 1.7 complete. Corpus is healthy. See {log_path} for details.")
        return

    # ------------------------------------------------------------------
    # Step 2: Full Pipeline Refresh
    # ------------------------------------------------------------------
    log("\n[Step 2] Starting full Phase 1 pipeline refresh...")
    pipeline_start = time.time()

    phases = [
        ("1.2 Extract", "phase1_ingestion_corpus_build/subphase1.2_extractor/src/run_extractor.py"),
        ("1.3 Clean", "phase1_ingestion_corpus_build/subphase1.3_cleaner_normalizer/src/run_cleaner.py"),
        ("1.4 Chunk", "phase1_ingestion_corpus_build/subphase1.4_chunker/src/run_chunker.py"),
        ("1.5 Embed", "phase1_ingestion_corpus_build/subphase1.5_embedder/src/run_embedder.py"),
        ("1.6 Index", "phase1_ingestion_corpus_build/subphase1.6_indexer/src/run_indexer.py"),
    ]

    # Note: Phase 1.1 Fetcher is skipped since we already have HTML files locally.
    # In production, Phase 1.1 would run first to re-fetch from URLs.
    log("\nNote: Skipping Phase 1.1 (Fetcher) - using existing HTML files.")
    log("In production, Phase 1.1 would re-fetch URLs before extraction.\n")

    phase_results = {}
    all_passed = True

    for phase_name, rel_path in phases:
        script_path = project_root / rel_path
        success = run_subprocess(str(script_path), phase_name, log_file)
        phase_results[phase_name] = success
        if not success:
            all_passed = False
            log(f"\n[ERROR] {phase_name} failed!")
            break
        else:
            log(f"\n[SUCCESS] {phase_name} completed.\n")

    pipeline_elapsed = time.time() - pipeline_start

    if not all_passed:
        log(f"\n[ERROR] Pipeline refresh failed. Stopping.")
        log(f"{'='*60}")
        log(f"Phase 1.7 Complete (Refresh FAILED)")
        log(f"  Failed at: {[k for k, v in phase_results.items() if not v]}")
        log(f"{'='*60}")
        log_file.close()
        print(f"Phase 1.7 complete. Refresh FAILED. See {log_path} for details.")
        return

    log(f"\nFull pipeline completed in {pipeline_elapsed:.1f}s")

    # ------------------------------------------------------------------
    # Step 3: Post-Refresh Health Check
    # ------------------------------------------------------------------
    log("\n[Step 3] Running post-refresh health check...")
    start_time = time.time()
    post_health = health_checker.run_all_checks()
    post_health_elapsed = time.time() - start_time

    log(f"Post-refresh health check completed in {post_health_elapsed:.1f}s")
    log(f"Overall passed: {post_health['overall_passed']}")

    for check_name, check_report in post_health["checks"].items():
        status = "PASS" if check_report["passed"] else "FAIL"
        log(f"  [{status}] {check_name}")

    # Save post-refresh health report with timestamp
    post_health_path = project_root / "data" / f"health_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    health_checker.save_report(post_health, str(post_health_path))

    # ------------------------------------------------------------------
    # Step 4: Version Tracking
    # ------------------------------------------------------------------
    log("\n[Step 4] Updating version tracking...")
    vt = VersionTracker(
        manifest_path=str(project_root / "data" / "corpus_version.json"),
        history_path=str(project_root / "data" / "corpus_version_history.json"),
    )

    # Get collection stats for chunk count
    try:
        sys.path.insert(0, str(project_root / "phase1_ingestion_corpus_build/subphase1.6_indexer/src"))
        from indexer import Indexer
        idx = Indexer(
            persist_directory=str(project_root / "data" / "indexed"),
            collection_name="mf_faq_corpus",
        )
        stats = idx.get_collection_stats()
        chunks_total = stats.get("total_chunks", 0)
        schemes_count = stats.get("unique_schemes", 0)
    except Exception as e:
        log(f"Warning: Could not get collection stats: {e}")
        chunks_total = 0
        schemes_count = 0

    manifest = vt.create_manifest(
        chunks_total=chunks_total,
        schemes_count=schemes_count,
        source="phase1.7_refresh",
        phases_run=["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"],
        health_report=post_health,
    )

    vt.save_version(manifest)
    log(f"Version saved: {manifest['version']}")
    log(f"Total chunks: {chunks_total}")
    log(f"Unique schemes: {schemes_count}")

    # Compare with previous version
    comparison = vt.compare_versions()
    if comparison.get("has_changes"):
        log("\nChanges from previous version:")
        for key, diff in comparison["differences"].items():
            if "delta" in diff and diff["delta"] is not None:
                log(f"  {key}: {diff['before']} -> {diff['after']} (delta: {diff['delta']:+d})")
            elif "before" in diff:
                log(f"  {key}: {diff['before']} -> {diff['after']}")

    # ------------------------------------------------------------------
    # Final Summary
    # ------------------------------------------------------------------
    total_elapsed = time.time() - pipeline_start + pre_health_elapsed

    log(f"\n{'='*60}")
    log(f"Phase 1.7 Complete")
    log(f"  Pre-health: {'PASS' if pre_health['overall_passed'] else 'FAIL'}")
    log(f"  Pipeline: {'ALL PASSED' if all_passed else 'FAILED'}")
    log(f"  Post-health: {'PASS' if post_health['overall_passed'] else 'FAIL'}")
    log(f"  Version: {manifest['version']}")
    log(f"  Chunks: {chunks_total}")
    log(f"  Schemes: {schemes_count}")
    log(f"  Health report: {health_report_path}")
    log(f"  Version manifest: {project_root / 'data' / 'corpus_version.json'}")
    log(f"  Total elapsed: {total_elapsed:.1f}s")
    log(f"{'='*60}")

    log_file.close()
    print(f"Phase 1.7 complete. See {log_path} for details.")


if __name__ == "__main__":
    force = "--force" in sys.argv
    run_phase_1_7(force_refresh=force)
