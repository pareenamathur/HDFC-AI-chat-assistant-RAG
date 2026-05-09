import sys
import os
import json
import logging

# Add src to path
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'src'))

from query_processor import QueryProcessor
from retriever import HybridRetriever
from context_builder import ContextBuilder

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Phase2Test")

def main():
    # 1. Load schemes
    chunked_data_path = os.path.join(os.path.dirname(BASE), 'data', 'processed', 'chunked_data_phase1.4.json')
    with open(chunked_data_path, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    scheme_names = sorted(list(set(c['scheme_name'] for c in chunks)))
    logger.info(f"Loaded {len(scheme_names)} schemes.")

    # 2. Initialize components
    qp = QueryProcessor(scheme_names)
    retriever = HybridRetriever(
        persist_directory=os.path.join(os.path.dirname(BASE), 'data', 'indexed'),
        collection_name="mf_faq_corpus"
    )
    builder = ContextBuilder()

    # 3. Test queries
    test_queries = [
        "What is the expense ratio of HDFC Balanced Advantage Fund?",
        "Tell me about the exit load for HDFC Flexi Cap Fund",
        "What is the risk level of HDFC Small Cap Fund?",
        "minimum sip for hdfc multi cap"
    ]

    for q in test_queries:
        logger.info(f"\n{'='*50}\nTESTING QUERY: {q}\n{'='*50}")
        
        # Step A: Process Query
        proc = qp.process_query(q)
        logger.info(f"Detected Filters: {proc['filters']}")
        logger.info(f"Detected Intent: {proc['intent']}")

        # Step B: Retrieve
        results = retriever.search(
            query=q, 
            n_results=3, 
            filters=proc['filters']
        )
        
        if not results:
            logger.warning("No results found!")
            continue

        for i, r in enumerate(results):
            logger.info(f"Result {i+1} [Score: {r['rerank_score']:.4f}]: {r['text'][:150]}...")

        # Step C: Build Context
        context = builder.build_context(results, intent=proc['intent'])
        logger.info("\n--- FINAL CONTEXT FOR LLM ---\n")
        print(context)
        print("\n" + "-"*50)

if __name__ == "__main__":
    main()
