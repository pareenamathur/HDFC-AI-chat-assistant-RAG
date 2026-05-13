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

logger = logging.getLogger(__name__)

class RAGOrchestrator:
    """Orchestrates the full RAG pipeline."""

    def __init__(
        self,
        persist_directory: str,
        scheme_names: list,
        use_bm25: bool = True,
        use_reranker: bool = True,
        vector_fetch_k: int = 12,
    ):
        self.qp = QueryProcessor(scheme_names)
        self.retriever = HybridRetriever(
            persist_directory=persist_directory,
            collection_name="mf_faq_corpus",
            use_bm25=use_bm25,
            use_reranker=use_reranker,
            vector_fetch_k=vector_fetch_k,
        )
        self.builder = ContextBuilder()
        self._generator = None

    def _get_generator(self):
        """Lazy LLM + AnswerGenerator so startup stays lightweight."""
        if self._generator is None:
            import gc
            from answer_generator import AnswerGenerator
            from llm_client import get_llm_provider
            self._generator = AnswerGenerator(get_llm_provider())
            gc.collect()
        return self._generator

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
        raw_answer = self._get_generator().generate_answer(query, context, multi_fund=is_multi)
        
        # 5. Post-process and apply URL Policy
        final_response = self._apply_policy(raw_answer, all_results)
        
        return final_response

    def _apply_policy(self, answer: str, results: list) -> Dict[str, Any]:
        """Ensures the response follows the URL and sentence constraints."""
        
        # Check if "don't know" or similar is in answer
        refusal_keywords = ["don't know", "do not have enough information", "not found", "cannot answer"]
        is_refusal = any(kw in answer.lower() for kw in refusal_keywords)

        # Strip ALL URLs from the answer to prevent broken links
        clean_answer = re.sub(r'https?://\S+', '', answer).strip()
        
        # Extract source information from chunk metadata
        source_info = None
        source_link = None
        last_updated = None
        
        if results and len(results) > 0:
            # Get the top result's metadata
            top_result = results[0]
            metadata = top_result.get("metadata", {})
            
            # Extract source information
            scheme_name = metadata.get("scheme_name", "Unknown Scheme")
            source_url = metadata.get("source_url", "")
            
            # Check if source_url is a local file or a valid URL
            if source_url and not source_url.startswith("http"):
                # It's a local file, don't use it as a link
                source_info = scheme_name
                source_link = None
            elif source_url and source_url.startswith("http"):
                # It's a valid URL
                source_info = scheme_name
                source_link = source_url
            else:
                # No source URL, just use scheme name
                source_info = scheme_name
                source_link = None
            
            # Get last updated date if available
            created_at = metadata.get("created_at", "")
            if created_at:
                try:
                    # Parse the datetime and format it
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    last_updated = dt.strftime("%Y-%m-%d")
                except:
                    last_updated = None
        
        # Apply user constraint: If we don't know, no source info.
        if is_refusal:
            return {
                "answer": clean_answer,
                "source": None,
                "source_link": None,
                "last_updated": None,
                "status": "refusal"
            }

        # Ensure sentence count (crude split) - allow 4 for multi-fund
        sentences = re.split(r'(?<=[.!?])\s+', clean_answer.strip())
        if len(sentences) > 4:
            clean_answer = " ".join(sentences[:4])

        return {
            "answer": clean_answer,
            "source": source_info,
            "source_link": source_link,
            "last_updated": last_updated,
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
