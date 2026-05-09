import sys
import os
import logging
import re
from typing import Dict, Any, Optional

# Add Phase 2 and Phase 3 src to path
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

from query_processor import QueryProcessor
from retriever import HybridRetriever
from context_builder import ContextBuilder
from answer_generator import AnswerGenerator
from llm_client import get_llm_provider

logger = logging.getLogger(__name__)

class RAGOrchestrator:
    """Orchestrates the full RAG pipeline."""

    def __init__(self, persist_directory: str, scheme_names: list):
        self.qp = QueryProcessor(scheme_names)
        self.retriever = HybridRetriever(
            persist_directory=persist_directory,
            collection_name="mf_faq_corpus"
        )
        self.builder = ContextBuilder()
        self.generator = AnswerGenerator(get_llm_provider())

    def answer_query(self, query: str) -> Dict[str, Any]:
        """Main entry point to get an answer."""
        
        # 1. Process Query
        proc = self.qp.process_query(query)
        filters = proc['filters']
        intent = proc['intent']

        # 2. Retrieve Chunks
        all_results = []
        is_multi = False
        
        # Check for multiple schemes
        if filters and "scheme_name" in filters:
            scheme_filter = filters["scheme_name"]
            if isinstance(scheme_filter, dict) and "$in" in scheme_filter:
                is_multi = True
                schemes = scheme_filter["$in"]
                logger.info(f"Multi-fund query detected. Schemes: {schemes}")
                
                # Retrieve chunks for each scheme to ensure context for all
                for scheme in schemes:
                    logger.info(f"Retrieving context for: {scheme}")
                    scheme_results = self.retriever.search(
                        query=query,
                        n_results=3, # 3 per fund
                        filters={"scheme_name": scheme}
                    )
                    all_results.extend(scheme_results)
            else:
                logger.info(f"Single-fund query detected: {scheme_filter}")
                all_results = self.retriever.search(
                    query=query,
                    n_results=4,
                    filters=filters
                )
        else:
            logger.info("No specific fund filter detected. Performing general search.")
            all_results = self.retriever.search(
                query=query,
                n_results=5,
                filters=None
            )

        if not all_results:
            return {
                "answer": "I'm sorry, I couldn't find any information about that in my records.",
                "source": None,
                "status": "no_results"
            }

        # 3. Build Context
        context = self.builder.build_context(all_results, intent=intent)

        # 4. Generate Response with Answer Generator (Groq)
        raw_answer = self.generator.generate_answer(query, context, multi_fund=is_multi)
        
        # 5. Post-process and apply URL Policy
        final_response = self._apply_policy(raw_answer, all_results)
        
        return final_response

    def _apply_policy(self, answer: str, results: list) -> Dict[str, Any]:
        """Ensures the response follows the URL and sentence constraints."""
        
        # Check if "don't know" or similar is in answer
        refusal_keywords = ["don't know", "do not have enough information", "not found", "cannot answer"]
        is_refusal = any(kw in answer.lower() for kw in refusal_keywords)

        # Extract ALL URLs if present
        urls = re.findall(r'https?://\S+', answer)
        primary_url = urls[0] if urls else None
        
        # Apply user constraint: If we don't know, no URL.
        if is_refusal:
            # Strip URLs if LLM included them by mistake
            clean_answer = re.sub(r'https?://\S+', '', answer).strip()
            return {
                "answer": clean_answer,
                "source": None,
                "status": "refusal"
            }

        # Ensure sentence count (crude split) - allow 4 for multi-fund
        sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
        if len(sentences) > 4:
            answer = " ".join(sentences[:4])
            # Re-append URLs if they were in the later sentences
            for url in urls:
                if url not in answer:
                    answer += f"\nSource: {url}"

        return {
            "answer": answer,
            "source": ", ".join(urls) if urls else None,
            "status": "success"
        }

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    # Mock scheme names
    schemes = ["HDFC Flexi Cap Fund", "HDFC Balanced Advantage Fund"]
    orch = RAGOrchestrator(persist_directory="data/indexed", scheme_names=schemes)
    
    print(orch.answer_query("What is the exit load for HDFC Flexi Cap?"))
    print("-" * 20)
    print(orch.answer_query("Should I buy HDFC Flexi Cap?"))
