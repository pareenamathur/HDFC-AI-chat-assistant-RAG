# Phase 0 — Foundation & Governance (Day 0) Edge Cases

*Focus: Scope definition, source validation, and guardrail establishment.*

---

## **EC 0.1: Broken or Redirected Links**
- **Scenario**: A Groww URL returns a 404 error or redirects to a generic search page because the scheme was renamed or merged.
- **Mitigation**: Implement a pre-indexing link validator script to flag dead URLs before the crawler starts.

---

## **EC 0.2: Groww Bot Detection**
- **Scenario**: Groww's CDN blocks the crawler due to high-frequency requests.
- **Mitigation**: Use custom headers (User-Agent), request throttling, and rotating proxies if necessary.

---

## **EC 0.3: Duplicate Schemes**
- **Scenario**: Different URLs pointing to the same underlying scheme but with different options (IDCW vs. Growth).
- **Mitigation**: Deduplicate based on the scheme's ISIN or specific name patterns during ingestion.

---

## **EC 0.4: Guardrail Ambiguity**
- **Scenario**: Unclear definition of what constitutes "investment advice" vs. factual information.
- **Mitigation**: Create explicit test cases with examples during Phase 0 to establish clear boundaries.

---

## **EC 0.5: Technical Stack Compatibility**
- **Scenario**: Selected tools (ChromaDB, OpenAI embeddings) have version conflicts or API changes.
- **Mitigation**: Pin specific versions in requirements.txt and test compatibility early in Phase 0.
