import re
from typing import Dict, List, Optional, Any
from thefuzz import process, fuzz


class QueryProcessor:
    """Processes user queries to extract scheme filters and intent."""

    # Stop-words ignored when building scheme fingerprints
    _STOP = {
        'hdfc', 'direct', 'plan', 'growth', 'nav', 'mutual',
        'performance', 'portfolio', 'index', 'fund', 'and', 'of',
        'the', 'equal', 'weight', 'top', 'fof', 'etf', 'bse',
    }

    # Intent keyword → metadata field mapping
    _INTENT_KEYWORDS = {
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

            # If primary check fails, try just the first token for short/single-word schemes
            # (e.g. "Pharma" fund when user says "HDFC Pharma Fund")
            if not matched and len(fp) >= 1:
                matched = fp[0] in query_lower

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

        # Fallback: no verbatim match — use fuzzy best-match
        if not found_schemes:
            best_match, score = process.extractOne(
                query, self.scheme_names, scorer=fuzz.partial_ratio
            )
            if score > 70:
                found_schemes = [best_match]

        if len(found_schemes) == 1:
            return {"scheme_name": found_schemes[0]}
        elif len(found_schemes) > 1:
            return {"scheme_name": {"$in": found_schemes}}
        return {}

    def detect_intent(self, query: str) -> Optional[str]:
        """Detects the specific factual data point being requested."""
        query_lower = query.lower()
        for kw, intent in self._INTENT_KEYWORDS.items():
            if kw in query_lower:
                return intent
        return None

    def process_query(self, query: str) -> Dict[str, Any]:
        """Main entry point for processing a query."""
        return {
            "original_query": query,
            "filters": self.extract_filters(query),
            "intent": self.detect_intent(query),
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
