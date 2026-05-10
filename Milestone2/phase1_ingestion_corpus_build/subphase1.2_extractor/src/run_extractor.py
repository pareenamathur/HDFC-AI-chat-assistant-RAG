"""
Run the Phase 1.2 Extractor to extract data from HTML files.
"""

import sys
import os
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from html_extractor import HTMLExtractor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run the extractor to process HTML files."""
    logger.info("Starting Phase 1.2 Extractor...")

    # Initialize extractor
    extractor = HTMLExtractor()

    # HTML files directory (relative to script location)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(script_dir))), 'data', 'html')
    processed_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(script_dir))), 'data', 'processed')
    
    os.makedirs(processed_dir, exist_ok=True)
    
    # Process all HTML files
    html_files = list(Path(html_dir).glob('*.html'))
    
    logger.info(f"Found {len(html_files)} HTML files to process")
    
    extracted_data = []
    
    for html_file in html_files:
        logger.info(f"Processing: {html_file.name}")
        
        try:
            # Read HTML file
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Extract data
            result = extractor.extract_html(html_content, str(html_file))
            
            extracted_data.append({
                'filename': html_file.name,
                'scheme_name': result.scheme_name,
                'text': result.text,
                'structured_data': result.structured_data,
                'document_links': result.document_links
            })
            
            logger.info(f"Extracted: {result.scheme_name}")
            
        except Exception as e:
            logger.error(f"Error processing {html_file.name}: {str(e)}")
    
    # Save extracted data to JSON
    output_file = os.path.join(processed_dir, 'extracted_data_phase1.2.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Extracted data saved to: {output_file}")
    logger.info(f"Phase 1.2 Extractor complete!")


if __name__ == "__main__":
    main()
