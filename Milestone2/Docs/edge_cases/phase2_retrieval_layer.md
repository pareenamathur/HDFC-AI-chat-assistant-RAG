# Phase 2 — Retrieval Layer Edge Cases

*Focus: Retrieval accuracy, efficiency, and relevance.*

---

## **EC 2.1: Semantic Overlap (Direct vs. Regular)**
- **Scenario**: The user asks for the "Expense Ratio," and the system retrieves data for both "Direct" and "Regular" plans without distinguishing them.
- **Mitigation**: Add mandatory plan-type metadata and prioritize "Direct" plans as per the project URLs.

---

## **EC 2.2: Embedding Collisions**
- **Scenario**: Queries for very similar funds (e.g., Nifty 50 vs. Nifty 50 Equal Weight) retrieve mixed contexts.
- **Mitigation**: Use "Self-RAG" techniques or Metadata Filtering where the scheme name must match the query intent exactly.

---

## **EC 2.3: Context Window Overflow**
- **Scenario**: Too many relevant chunks are retrieved, exceeding the LLM's context limit.
- **Mitigation**: Implement Reranking (e.g., Cohere Rerank) to select the top 3 most relevant chunks.

---

## **EC 2.4: Low Similarity Scores**
- **Scenario**: Retrieval score is below threshold (0.7) but LLM still attempts to answer.
- **Mitigation**: Hard threshold enforcement to trigger "I don't have enough verified information" refusal.

---

## **EC 2.5: Query Ambiguity**
- **Scenario**: User query is too vague (e.g., "What about HDFC?").
- **Mitigation**: Implement query clarification prompts or return top scheme options for user to select.
