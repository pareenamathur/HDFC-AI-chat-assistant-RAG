import sys
sys.path.insert(0, 'phase2_retrieval_layer/src')
from query_processor import QueryProcessor

import chromadb
client = chromadb.PersistentClient(path='data/indexed')
col = client.get_collection('mf_faq_corpus')
all_meta = col.get(include=['metadatas'])['metadatas']
scheme_names = list({m['scheme_name'] for m in all_meta})
print(f"Corpus schemes ({len(scheme_names)}):")
for s in sorted(scheme_names):
    print(f"  - {s}")
print()

qp = QueryProcessor(scheme_names)

queries = [
    "Compare expense ratios of HDFC Flexi Cap and HDFC Small Cap Fund",
    "What is the exit load for HDFC Balanced Advantage and HDFC Gold ETF?",
    "What is the NAV of HDFC Pharma Fund?",
    "Compare HDFC Multi Cap and HDFC Mid Cap Fund",
]
for q in queries:
    result = qp.process_query(q)
    print(f"Q: {q}")
    print(f"   filters: {result['filters']}")
    print(f"   intent:  {result['intent']}")
    print()
