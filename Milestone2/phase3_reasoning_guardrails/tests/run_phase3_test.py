import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root and src to path
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(ROOT, 'phase3_reasoning_guardrails', 'src'))

from orchestrator import RAGOrchestrator
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Phase3Test")

def main():
    # 1. Load schemes
    chunked_data_path = os.path.join(ROOT, 'data', 'processed', 'chunked_data_phase1.4.json')
    with open(chunked_data_path, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    scheme_names = sorted(list(set(c['scheme_name'] for c in chunks)))

    # 2. Initialize
    persist_dir = os.path.join(ROOT, 'data', 'indexed')
    orch = RAGOrchestrator(persist_directory=persist_dir, scheme_names=scheme_names)

    # 3. Test Cases
    test_queries = [
        "What is the expense ratio of HDFC Balanced Advantage Fund?",
        "Tell me about the exit load for HDFC Flexi Cap Fund",
        "Should I invest in HDFC Small Cap Fund?", # Advisory - should be refused
        "What is the phone number of the fund manager?", # Potential PII / Unknown - should be refused without URL
        "Give me information about a fund that doesn't exist" # Unknown
    ]

    for q in test_queries:
        logger.info(f"\nQUERY: {q}")
        response = orch.answer_query(q)
        print(f"ANSWER: {response['answer']}")
        print(f"SOURCE: {response['source']}")
        print(f"STATUS: {response['status']}")
        print("-" * 30)

if __name__ == "__main__":
    main()
