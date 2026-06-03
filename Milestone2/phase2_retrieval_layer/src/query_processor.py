import logging
import re
from typing import Dict, List, Optional, Any
from thefuzz import process, fuzz

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Processes user queries to extract scheme filters and intent."""

    # Stop-words ignored when building scheme fingerprints
    _STOP = {
        'hdfc', 'direct', 'plan', 'growth', 'nav', 'mutual',
        'performance', 'portfolio', 'index', 'fund', 'and', 'of',
        'the', 'equal', 'weight', 'fof', 'etf', 'bse',
        # NOTE: do not include 'top' — needed to distinguish "HDFC Top 100" vs funds that only share "100"
    }

    # Intent keyword → metadata field mapping
    _INTENT_KEYWORDS = {
        "top holding": "holdings",
        "holdings": "holdings",
        "portfolio holding": "holdings",
        "equity exposure": "equity_exposure",
        "equity allocation": "equity_exposure",
        "stock exposure": "equity_exposure",
        "expense": "expense_ratio",
        "exit": "exit_load",
        "load": "exit_load",
        "nav": "nav",
        "aum": "aum",
        "fund size": "aum",
        "sip": "sip_minimum",
        "minimum": "sip_minimum",
        "risk": "risk_level",
        "category": "category",
        "benchmark": "benchmark",
        "sid": "sid",
        "kim": "kim",
    }

    def __init__(self, scheme_names: List[str]):
        self.scheme_names = scheme_names
        # Pre-compute fingerprints once for efficiency
        self._fingerprints: Dict[str, List[str]] = {
            s: self._scheme_fingerprint(s) for s in scheme_names
        }

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _scheme_fingerprint(self, scheme_full_name: str) -> List[str]:
        """
        Extract distinctive tokens from a long scheme name.
        'HDFC Flexi Cap Direct Plan Growth - NAV...' → ['flexi', 'cap']
        """
        tokens = re.findall(r'[a-z0-9]+', scheme_full_name.lower())
        return [t for t in tokens if t not in self._STOP]

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def extract_filters(self, query: str) -> Dict[str, Any]:
        """
        Identify which scheme(s) the user is asking about.

        Strategy
        --------
        1. For every scheme, check whether its first 2 distinctive tokens
           both appear in the query (verbatim word match).  This reliably
           detects "HDFC Flexi Cap" and "HDFC Small Cap" in the same query.
        2. If zero schemes matched that way, fall back to fuzzy best-match
           (handles typos / partial names).
        """
        query_lower = query.lower()
        found_schemes: List[str] = []

        for scheme, fp in self._fingerprints.items():
            if not fp:
                continue

            # Primary check: first 2 distinctive tokens must all appear in the query
            key_tokens = fp[:2]
            matched = all(tok in query_lower for tok in key_tokens)

            # Single-token fallback only when the query is short or names one distinctive token
            if not matched and len(fp) == 1:
                matched = fp[0] in query_lower
            elif not matched and len(fp) >= 2:
                matched = sum(1 for tok in fp[:3] if tok in query_lower) >= 2

            if matched:
                found_schemes.append(scheme)

        # Sort most-specific first (longer fingerprint = more distinctive)
        found_schemes.sort(key=lambda s: len(self._fingerprints[s]), reverse=True)

        # De-duplicate: two schemes are duplicates only if their fingerprint tokens
        # are nearly identical (e.g. 'Nifty 50' vs 'Nifty 50 Index' – keep the more specific)
        # We compare fingerprint sets, not full names (fixes 'Flexi Cap' vs 'Small Cap')
        deduped: List[str] = []
        for s in found_schemes:
            s_fp = set(self._fingerprints[s])
            # Consider a duplicate only if fingerprint intersection covers >80% of the shorter set
            is_dup = False
            for existing in deduped:
                e_fp = set(self._fingerprints[existing])
                shorter = min(len(s_fp), len(e_fp))
                if shorter > 0 and len(s_fp & e_fp) / shorter > 0.8:
                    is_dup = True
                    break
            if not is_dup:
                deduped.append(s)
        found_schemes = deduped

        # Avoid matching half the corpus via a single weak token (e.g. "100") → huge $in lists / Chroma stress
        if len(found_schemes) > 8:
            logger.warning(
                "extract_filters: %s schemes matched query; capping to 8 most-specific (longest fingerprints)",
                len(found_schemes),
            )
            found_schemes = found_schemes[:8]

        # Fallback: no verbatim match — use fuzzy best-match
        if not found_schemes:
            # Empty scheme list (e.g. chunked_data missing on deploy) makes extractOne raise —
            # warm_vector_pipeline still succeeds because it skips process_query filters.
            if not self.scheme_names:
                logger.warning(
                    "QueryProcessor.extract_filters: scheme_names is empty — cannot fuzzy-match schemes. "
                    "Ensure data/processed/chunked_data_phase1.4.json exists and PROCESSED_DATA_PATH resolves on the server."
                )
                return {}
            try:
                result = process.extractOne(
                    query, self.scheme_names, scorer=fuzz.partial_ratio
                )
            except (ValueError, TypeError) as e:
                logger.warning("QueryProcessor.extract_filters: fuzzy extractOne failed: %s", e)
                return {}
            if result is None:
                return {}
            best_match, score = result
            if score > 70 and best_match is not None:
                q_tokens = set(re.findall(r"[a-z0-9]+", query_lower)) - self._STOP
                match_tokens = set(self._fingerprints.get(best_match, []))
                overlap = len(q_tokens & match_tokens)
                # Require at least two distinctive token overlaps (avoids "Top 100" → "Nifty Top 20")
                if overlap >= 2 or (overlap >= 1 and len(match_tokens) == 1):
                    found_schemes = [best_match]
                else:
                    logger.info(
                        "extract_filters: rejected fuzzy match %r (score=%s overlap=%s)",
                        best_match,
                        score,
                        overlap,
                    )

        if len(found_schemes) == 1:
            return {"scheme_name": found_schemes[0]}
        elif len(found_schemes) > 1:
            return {"scheme_name": {"$in": found_schemes}}
        return {}

    _ATTRIBUTE_PATTERNS = (
        ("expense_ratio", ("expense ratio", "ter", "expense")),
        ("aum", ("fund size", "aum", "asset under management", "corpus size")),
        ("nav", ("nav", "net asset value")),
        ("holdings", ("top holding", "holdings", "portfolio holding", "constituent")),
        ("equity_exposure", ("equity exposure", "equity allocation", "stock exposure")),
        ("exit_load", ("exit load",)),
        ("risk_level", ("risk level", "riskometer", "risk rating")),
    )

    @classmethod
    def detect_requested_attributes(cls, query: str) -> List[str]:
        """All factual attributes explicitly requested (not mutually exclusive)."""
        q = (query or "").lower()
        found: List[str] = []
        for attr, phrases in cls._ATTRIBUTE_PATTERNS:
            if any(p in q for p in phrases):
                found.append(attr)
        return found

    @classmethod
    def is_comparison_query(cls, query: str) -> bool:
        q = (query or "").lower()
        return any(
            k in q
            for k in (
                "compare",
                "comparison",
                " versus ",
                " vs ",
                " vs.",
                "difference between",
            )
        )

    def detect_intent(self, query: str) -> Optional[str]:
        """Primary intent — first requested attribute, else keyword scan."""
        attrs = self.detect_requested_attributes(query)
        if attrs:
            return attrs[0]
        query_lower = query.lower()
        for kw, intent in sorted(self._INTENT_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if kw in query_lower:
                return intent
        return None

    def process_query(self, query: str) -> Dict[str, Any]:
        """Main entry point for processing a query."""
        filters = self.extract_filters(query)
        return {
            "original_query": query,
            "filters": filters,
            "intent": self.detect_intent(query),
            "requested_attributes": self.detect_requested_attributes(query),
            "is_comparison": self.is_comparison_query(query),
            "normalized_query": self._normalize(query),
        }

    def _normalize(self, query: str) -> str:
        """Normalizes the query for better search matching."""
        query = query.lower()
        query = re.sub(r'[^a-z0-9\s]', '', query)
        return query.strip()


if __name__ == "__main__":
    # Quick self-test
    schemes = [
        "HDFC Balanced Advantage Fund Direct Growth - NAV, Mutual Fund Performance & Portfolio",
        "HDFC Flexi Cap Direct Plan Growth - NAV, Mutual Fund Performance & Portfolio",
        "HDFC Small Cap Fund Direct Growth - NAV, Mutual Fund Performance & Portfolio",
        "HDFC Gold ETF Fund of Fund Direct Plan Growth - NAV, Mutual Fund Performance & Portfolio",
    ]
    qp = QueryProcessor(schemes)

    test_queries = [
        "Compare expense ratios of HDFC Flexi Cap and HDFC Small Cap Fund",
        "What is the exit load for HDFC Balanced Advantage and HDFC Gold ETF?",
        "What is the NAV of HDFC Flexi Cap?",
        "minimum sip amount for hdfc balanced advantage",
    ]

    for q in test_queries:
        result = qp.process_query(q)
        print(f"Q: {q}")
        print(f"   filters: {result['filters']}")
        print(f"   intent:  {result['intent']}")
        print("-" * 60)
