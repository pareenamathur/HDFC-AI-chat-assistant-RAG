"""
Health Checker Module - Phase 1.7
Monitors corpus freshness, validates integrity, and runs retrieval sanity checks.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class HealthChecker:
    """Performs health checks on the indexed corpus."""

    def __init__(
        self,
        corpus_version_path: str = "../../data/corpus_version.json",
        chroma_persist_dir: str = "../../data/indexed",
        collection_name: str = "mf_faq_corpus",
        stale_threshold_days: int = 30,
        embedding_model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        self.corpus_version_path = Path(corpus_version_path)
        self.chroma_persist_dir = Path(chroma_persist_dir)
        self.collection_name = collection_name
        self.stale_threshold_days = stale_threshold_days
        self.embedding_model_name = embedding_model_name
        self._indexer = None

    def _get_indexer(self):
        """Lazy-load the indexer for health checks."""
        if self._indexer is None:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../subphase1.6_indexer/src"))
            from indexer import Indexer
            self._indexer = Indexer(
                persist_directory=str(self.chroma_persist_dir),
                collection_name=self.collection_name,
                embedding_model_name=self.embedding_model_name,
            )
        return self._indexer

    # ------------------------------------------------------------------
    # Freshness Check
    # ------------------------------------------------------------------
    def check_freshness(self) -> Dict[str, Any]:
        """
        Check if the corpus is stale based on last_updated date.

        Returns:
            Freshness report dict
        """
        report = {
            "check": "freshness",
            "passed": False,
            "last_updated": None,
            "age_days": None,
            "stale_threshold_days": self.stale_threshold_days,
            "errors": [],
        }

        try:
            if not self.corpus_version_path.exists():
                report["errors"].append(f"Corpus version manifest not found: {self.corpus_version_path}")
                return report

            with open(self.corpus_version_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            last_updated_str = manifest.get("last_updated")
            if not last_updated_str:
                report["errors"].append("Missing 'last_updated' field in corpus_version.json")
                return report

            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(timezone.utc)
            age = now - last_updated
            age_days = age.days

            report["last_updated"] = last_updated.isoformat()
            report["age_days"] = age_days
            report["passed"] = age_days <= self.stale_threshold_days

            if not report["passed"]:
                report["errors"].append(
                    f"Corpus is stale: {age_days} days old (threshold: {self.stale_threshold_days})"
                )

        except json.JSONDecodeError as e:
            report["errors"].append(f"Invalid JSON in corpus_version.json: {e}")
        except Exception as e:
            report["errors"].append(f"Freshness check error: {e}")

        return report

    # ------------------------------------------------------------------
    # Integrity Check
    # ------------------------------------------------------------------
    def check_integrity(self) -> Dict[str, Any]:
        """
        Validate ChromaDB index integrity using the Indexer's validation.

        Returns:
            Integrity report dict
        """
        report = {
            "check": "integrity",
            "passed": False,
            "total_chunks": 0,
            "errors": [],
        }

        try:
            indexer = self._get_indexer()
            validation = indexer.validate_index()

            report["passed"] = validation["is_valid"]
            report["total_chunks"] = validation["total_chunks"]
            report["checks"] = validation.get("checks", {})

            if not report["passed"]:
                for err in validation.get("errors", []):
                    report["errors"].append(err)

        except Exception as e:
            report["errors"].append(f"Integrity check error: {e}")

        return report

    # ------------------------------------------------------------------
    # Retrieval Sanity Check
    # ------------------------------------------------------------------
    def check_retrieval(self, test_queries: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run test queries to verify retrieval quality.

        Args:
            test_queries: List of test queries. Uses defaults if None.

        Returns:
            Retrieval sanity report dict
        """
        report = {
            "check": "retrieval",
            "passed": False,
            "queries_tested": 0,
            "queries_passed": 0,
            "min_similarity_threshold": 0.5,
            "results": [],
            "errors": [],
        }

        default_queries = [
            "What is the expense ratio of HDFC Balanced Advantage Fund?",
            "What is the exit load for HDFC Flexi Cap Fund?",
            "What is the risk level of HDFC Small Cap Fund?",
            "Tell me about HDFC Gold ETF Fund",
            "What is the NAV of HDFC Nifty 50 Index Fund?",
        ]

        queries = test_queries or default_queries
        report["queries_tested"] = len(queries)

        try:
            indexer = self._get_indexer()
            passed_count = 0

            for query in queries:
                query_report = {
                    "query": query,
                    "passed": False,
                    "top_similarity": None,
                    "top_scheme": None,
                    "error": None,
                }

                try:
                    results = indexer.query_by_text(query, n_results=1)
                    if len(results["ids"][0]) == 0:
                        query_report["error"] = "No results returned"
                    else:
                        similarity = 1 - results["distances"][0][0]
                        scheme = results["metadatas"][0][0].get("scheme_name", "Unknown")
                        query_report["top_similarity"] = round(similarity, 4)
                        query_report["top_scheme"] = scheme
                        query_report["passed"] = similarity >= report["min_similarity_threshold"]
                        if query_report["passed"]:
                            passed_count += 1
                except Exception as e:
                    query_report["error"] = str(e)

                report["results"].append(query_report)

            report["queries_passed"] = passed_count
            report["passed"] = passed_count == len(queries)

        except Exception as e:
            report["errors"].append(f"Retrieval check error: {e}")

        return report

    # ------------------------------------------------------------------
    # Metadata Coverage Check
    # ------------------------------------------------------------------
    def check_metadata_coverage(self) -> Dict[str, Any]:
        """
        Check that all chunks have required metadata fields.

        Returns:
            Metadata coverage report dict
        """
        report = {
            "check": "metadata_coverage",
            "passed": False,
            "total_chunks": 0,
            "required_fields": ["scheme_name", "document_type", "category", "section"],
            "field_coverage": {},
            "errors": [],
        }

        required = report["required_fields"]

        try:
            indexer = self._get_indexer()
            collection = indexer._get_or_create_collection()
            total = collection.count()
            report["total_chunks"] = total

            if total == 0:
                report["errors"].append("Collection is empty")
                return report

            # Sample all metadata
            all_data = collection.get(include=["metadatas"])
            metadatas = all_data["metadatas"]

            for field in required:
                present = sum(1 for m in metadatas if m.get(field))
                report["field_coverage"][field] = {
                    "present": present,
                    "missing": total - present,
                    "coverage_pct": round(present / total * 100, 1),
                }

            # Check if all fields have 100% coverage
            all_complete = all(
                report["field_coverage"][f]["coverage_pct"] == 100.0
                for f in required
            )
            report["passed"] = all_complete

            if not all_complete:
                for field in required:
                    cov = report["field_coverage"][field]
                    if cov["coverage_pct"] < 100:
                        report["errors"].append(
                            f"Field '{field}': {cov['missing']}/{total} chunks missing ({cov['coverage_pct']}% coverage)"
                        )

        except Exception as e:
            report["errors"].append(f"Metadata coverage check error: {e}")

        return report

    # ------------------------------------------------------------------
    # URL Health Check
    # ------------------------------------------------------------------
    def check_urls(self, urls_config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if whitelisted URLs are reachable.

        Args:
            urls_config_path: Path to urls.yaml. Uses default if None.

        Returns:
            URL health report dict
        """
        report = {
            "check": "urls",
            "passed": False,
            "total_urls": 0,
            "reachable": 0,
            "failed": 0,
            "failure_rate_pct": 0.0,
            "results": [],
            "errors": [],
        }

        try:
            import requests
            import yaml

            if urls_config_path is None:
                urls_config_path = os.path.join(
                    os.path.dirname(__file__),
                    "../../subphase1.1_fetcher/config/urls.yaml"
                )

            with open(urls_config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            urls = config.get("urls", [])
            report["total_urls"] = len(urls)

            if len(urls) == 0:
                report["errors"].append("No URLs found in config")
                return report

            headers = {"User-Agent": "MF-FAQ-HealthCheck/1.0"}
            failed = 0

            for url_entry in urls:
                url = url_entry.get("url", "") if isinstance(url_entry, dict) else str(url_entry)
                url_report = {
                    "url": url[:80] + "..." if len(url) > 80 else url,
                    "status_code": None,
                    "reachable": False,
                    "error": None,
                }

                try:
                    resp = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
                    url_report["status_code"] = resp.status_code
                    url_report["reachable"] = resp.status_code < 400
                    if not url_report["reachable"]:
                        failed += 1
                        url_report["error"] = f"HTTP {resp.status_code}"
                except requests.RequestException as e:
                    failed += 1
                    url_report["error"] = str(e)

                report["results"].append(url_report)

            report["reachable"] = report["total_urls"] - failed
            report["failed"] = failed
            report["failure_rate_pct"] = round(failed / report["total_urls"] * 100, 1)
            # Pass if failure rate is < 10%
            report["passed"] = report["failure_rate_pct"] < 10.0

        except ImportError as e:
            report["errors"].append(f"Missing dependency: {e}")
        except Exception as e:
            report["errors"].append(f"URL check error: {e}")

        return report

    # ------------------------------------------------------------------
    # Full Health Report
    # ------------------------------------------------------------------
    def run_all_checks(
        self,
        test_queries: Optional[List[str]] = None,
        urls_config_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run all health checks and return a comprehensive report.

        Returns:
            Full health report with all checks
        """
        start_time = time.time()

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_passed": False,
            "checks": {},
            "summary": {
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 0,
            },
            "elapsed_seconds": 0,
        }

        checks = [
            ("freshness", self.check_freshness()),
            ("integrity", self.check_integrity()),
            ("metadata_coverage", self.check_metadata_coverage()),
            ("retrieval", self.check_retrieval(test_queries)),
            ("urls", self.check_urls(urls_config_path)),
        ]

        passed_count = 0
        for name, check_report in checks:
            report["checks"][name] = check_report
            report["summary"]["total_checks"] += 1
            if check_report.get("passed", False):
                passed_count += 1

        report["summary"]["passed_checks"] = passed_count
        report["summary"]["failed_checks"] = report["summary"]["total_checks"] - passed_count
        report["overall_passed"] = passed_count == report["summary"]["total_checks"]
        report["elapsed_seconds"] = round(time.time() - start_time, 2)

        return report

    def save_report(self, report: Dict[str, Any], output_path: str) -> None:
        """Save health report to JSON file."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Quick self-test
    hc = HealthChecker()
    report = hc.run_all_checks()
    print(f"Overall passed: {report['overall_passed']}")
    print(f"Checks: {report['summary']}")
