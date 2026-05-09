"""End-to-end runner for Phase 1.1 through 1.4 pipeline."""
import json, time, sys, os, logging

logging.disable(logging.CRITICAL)

BASE = os.path.dirname(os.path.abspath(__file__))

def run_phase_1_2():
    """Phase 1.2: Extract data from HTML files."""
    sys.path.insert(0, os.path.join(BASE, 'phase1_ingestion_corpus_build', 'subphase1.2_extractor', 'src'))
    from html_extractor import HTMLExtractor
    from pathlib import Path

    extractor = HTMLExtractor()
    html_dir = os.path.join(BASE, 'data', 'html')
    processed_dir = os.path.join(BASE, 'data', 'processed')
    os.makedirs(processed_dir, exist_ok=True)

    html_files = sorted(Path(html_dir).glob('*.html'))
    results = []
    for hf in html_files:
        with open(hf, 'r', encoding='utf-8') as f:
            html = f.read()
        r = extractor.extract_html(html, str(hf))
        results.append({
            'filename': hf.name,
            'scheme_name': r.scheme_name,
            'text': r.text,
            'structured_data': r.structured_data,
            'document_links': r.document_links,
        })

    out = os.path.join(processed_dir, 'extracted_data_phase1.2.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return len(results), out


def run_phase_1_3():
    """Phase 1.3: Clean and normalize extracted data."""
    # Reimport with fresh path
    import importlib
    mod_dir = os.path.join(BASE, 'phase1_ingestion_corpus_build', 'subphase1.3_cleaner_normalizer', 'src')
    if mod_dir in sys.path:
        sys.path.remove(mod_dir)
    sys.path.insert(0, mod_dir)

    # Force reimport
    for mod in list(sys.modules.keys()):
        if 'data_cleaner' in mod or 'metadata_tagger' in mod:
            del sys.modules[mod]
    from data_cleaner import DataCleaner
    from metadata_tagger import MetadataTagger

    cleaner = DataCleaner()
    tagger = MetadataTagger()
    processed_dir = os.path.join(BASE, 'data', 'processed')

    with open(os.path.join(processed_dir, 'extracted_data_phase1.2.json'), 'r', encoding='utf-8') as f:
        extracted = json.load(f)

    cleaned = []
    for doc in extracted:
        cr = cleaner.clean_text(doc['text'])
        text = cr.cleaned_text
        text = cleaner.remove_headers_footers(text)
        text = cleaner.normalize_dates(text)
        cm = cleaner.clean_metadata(doc.get('structured_data', {}))

        tagged = tagger.tag_document(
            scheme_name=doc['scheme_name'],
            document_type='webpage',
            source_url=doc['filename'],
            content=text,
            category='mutual_fund',
            additional_metadata=cm,
        )
        cleaned.append({
            'filename': doc['filename'],
            'scheme_name': doc['scheme_name'],
            'text': text,
            'cleaned_metadata': cm,
            'document_id': tagged.document_id,
            'metadata': tagged.metadata,
            'content_hash': tagged.content_hash,
        })

    out = os.path.join(processed_dir, 'cleaned_data_phase1.3.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    return len(cleaned), out


def run_phase_1_4():
    """Phase 1.4: Chunk cleaned data."""
    mod_dir = os.path.join(BASE, 'phase1_ingestion_corpus_build', 'subphase1.4_chunker', 'src')
    if mod_dir in sys.path:
        sys.path.remove(mod_dir)
    sys.path.insert(0, mod_dir)
    for mod in list(sys.modules.keys()):
        if 'chunker' in mod and 'phase1' in mod:
            del sys.modules[mod]
    from chunker import Chunker

    chunker = Chunker(min_chunk_size=50, max_chunk_size=1000, chunk_overlap=100)
    processed_dir = os.path.join(BASE, 'data', 'processed')

    with open(os.path.join(processed_dir, 'cleaned_data_phase1.3.json'), 'r', encoding='utf-8') as f:
        cleaned = json.load(f)

    all_chunks = []
    for doc in cleaned:
        chunks = chunker.chunk_document(
            text=doc['text'],
            sections={},
            structured_data=doc['cleaned_metadata'],
            document_metadata=doc['metadata'],
        )
        for c in chunks:
            all_chunks.append({
                'chunk_id': c.chunk_id,
                'text': c.text,
                'section': c.section,
                'source_document_id': c.source_document_id,
                'metadata': c.metadata,
                'structured_data': c.structured_data,
                'scheme_name': doc['scheme_name'],
            })

    out = os.path.join(processed_dir, 'chunked_data_phase1.4.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    return len(all_chunks), out


def validate():
    """Validate end-to-end outputs."""
    processed_dir = os.path.join(BASE, 'data', 'processed')
    errors = []

    # Phase 1.2
    with open(os.path.join(processed_dir, 'extracted_data_phase1.2.json'), 'r', encoding='utf-8') as f:
        ext = json.load(f)
    if len(ext) != 15:
        errors.append(f"Phase 1.2: Expected 15 docs, got {len(ext)}")
    # Check structured_data quality
    bad_exit = [d['scheme_name'] for d in ext if d.get('structured_data', {}).get('exit_load', '') in ('01', '22', '')]
    if bad_exit:
        errors.append(f"Phase 1.2: Bad exit_load for: {bad_exit[:3]}...")

    # Phase 1.3
    with open(os.path.join(processed_dir, 'cleaned_data_phase1.3.json'), 'r', encoding='utf-8') as f:
        cln = json.load(f)
    # Check for corrupted text (no "expense_ratiom" artifact)
    corrupted = [d['scheme_name'][:30] for d in cln if 'expense_ratiom' in d['text']]
    if corrupted:
        errors.append(f"Phase 1.3: Text corruption detected in {len(corrupted)} docs")
    if len(cln) != 15:
        errors.append(f"Phase 1.3: Expected 15 docs, got {len(cln)}")

    # Phase 1.4
    with open(os.path.join(processed_dir, 'chunked_data_phase1.4.json'), 'r', encoding='utf-8') as f:
        chk = json.load(f)
    sizes = [len(c['text']) for c in chk]
    min_v = sum(1 for s in sizes if s < 50)
    max_v = sum(1 for s in sizes if s > 1000)
    if min_v > 0:
        errors.append(f"Phase 1.4: {min_v} chunks below 50 chars")
    if max_v > 0:
        errors.append(f"Phase 1.4: {max_v} chunks above 1000 chars")

    return errors


if __name__ == '__main__':
    log = []
    t_total = time.time()

    # --- Phase 1.1 (already have HTML files) ---
    html_dir = os.path.join(BASE, 'data', 'html')
    html_count = len([f for f in os.listdir(html_dir) if f.endswith('.html')])
    log.append(f"Phase 1.1: {html_count} HTML files present in data/html/ (pre-fetched)")

    # --- Phase 1.2 ---
    t0 = time.time()
    n12, f12 = run_phase_1_2()
    log.append(f"Phase 1.2: Extracted {n12} documents -> {os.path.basename(f12)} ({time.time()-t0:.2f}s)")

    # --- Phase 1.3 ---
    t0 = time.time()
    n13, f13 = run_phase_1_3()
    log.append(f"Phase 1.3: Cleaned {n13} documents -> {os.path.basename(f13)} ({time.time()-t0:.2f}s)")

    # --- Phase 1.4 ---
    t0 = time.time()
    n14, f14 = run_phase_1_4()
    log.append(f"Phase 1.4: Created {n14} chunks -> {os.path.basename(f14)} ({time.time()-t0:.2f}s)")

    # --- Validation ---
    errors = validate()

    log.append(f"\nTotal pipeline time: {time.time()-t_total:.2f}s")
    log.append(f"\n--- Validation ---")
    if errors:
        for e in errors:
            log.append(f"  ERROR: {e}")
    else:
        log.append("  All checks passed!")

    # Print to stdout
    for line in log:
        print(line)

    # Also write to file
    with open(os.path.join(BASE, 'pipeline_run.log'), 'w') as f:
        f.write('\n'.join(log))
