#!/usr/bin/env python
# encoding: utf-8

import json
import re
import os
import logging
from pathlib import Path
import argparse
import glob

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import PyMuPDF but provide helpful message if not installed
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    logger.warning("PyMuPDF not found. Install with: pip install pymupdf")
    PYMUPDF_AVAILABLE = False


def load_json(file_path):
    """Load JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def save_json(data, file_path):
    """Save data to JSON file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def clean_title(title, corrected_toc=None):
    """Clean up title based on corrected TOC if available."""
    # Basic cleaning
    title = re.sub(r'\s+', ' ', title.strip())
    
    # Use corrected TOC if available
    if corrected_toc:
        # Handle different possible structures
        if isinstance(corrected_toc, dict):
            # If it's a direct mapping dictionary
            if title.lower() in [k.lower() for k in corrected_toc.keys()]:
                for k, v in corrected_toc.items():
                    if k.lower() == title.lower():
                        return v
        elif isinstance(corrected_toc, list):
            # If it's a list of items
            for item in corrected_toc:
                if isinstance(item, dict):
                    # Check for original/corrected keys
                    orig = item.get('original', '')
                    if isinstance(orig, str) and orig.lower() == title.lower():
                        return item.get('corrected', title)
    
    return title


def has_multiple_tables_indicator(title):
    """
    Check if a title might indicate multiple tables.
    This is now just a preliminary check - actual PDF verification is preferred.
    """
    # Simple indicators
    has_and = ' and ' in title.lower()
    has_comma = ',' in title
    
    # Simple exclusions (common phrases that don't indicate separate tables)
    exclusions = [
        "and minnesota", 
        "and average", 
        "x mallard"
    ]
    
    if has_and or has_comma:
        # Check exclusions
        if any(excl in title.lower() for excl in exclusions):
            logger.info(f"Title has 'and'/comma but matches exclusion pattern: {title}")
            return False
        logger.info(f"Title might indicate multiple tables: {title}")
        return True
    
    return False


def split_table_title(title):
    """Split a title that contains multiple table references."""
    if ' and ' in title.lower():
        parts = re.split(r'\s+and\s+', title, flags=re.IGNORECASE)
        return [part.strip() for part in parts]
    elif ',' in title:
        return [part.strip() for part in title.split(',')]
    return [title]  # Return original if no split is possible


def find_pdf_for_item(item, pdf_dirs):
    """
    Attempt to find the PDF file for an item by checking multiple possible locations.
    
    Args:
        item: The metadata item
        pdf_dirs: List of directories to check for PDFs
        
    Returns:
        The path to the PDF if found, None otherwise
    """
    # Check if the item has explicit year information
    if 'year' in item and item['year']:
        year = str(item['year'])
        
        # Try different naming patterns
        pdf_names = [
            f"{year}.pdf",
            f"CF_{year}.pdf", 
            f"Central_Flyway_{year}.pdf",
            f"*{year}*.pdf"  # Fallback to any PDF with year in the name
        ]
        
        # Check each directory and naming pattern
        for pdf_dir in pdf_dirs:
            for pdf_name in pdf_names:
                # Handle glob patterns
                if '*' in pdf_name:
                    matching_files = glob.glob(os.path.join(pdf_dir, pdf_name))
                    if matching_files:
                        return matching_files[0]
                else:
                    pdf_path = os.path.join(pdf_dir, pdf_name)
                    if os.path.exists(pdf_path):
                        return pdf_path
    
    # Check for explicit filename
    if 'file_name' in item and item['file_name']:
        file_name = item['file_name']
        for pdf_dir in pdf_dirs:
            pdf_path = os.path.join(pdf_dir, file_name)
            if os.path.exists(pdf_path):
                return pdf_path
    
    # Check for explicit path
    if 'path' in item and item['path']:
        if os.path.exists(item['path']):
            return item['path']
    
    # No PDF found
    return None


def detect_tables_in_page(pdf_path, page_number):
    """
    Analyze PDF page to detect multiple tables and their positions.
    Returns a list of table positions as (top, bottom) vertical coordinates.
    """
    if not PYMUPDF_AVAILABLE:
        logger.warning("PyMuPDF not available - assuming single table per page")
        return [(0.0, 1.0)]
    
    if not os.path.exists(pdf_path):
        logger.warning(f"PDF not found: {pdf_path} - assuming single table per page")
        return [(0.0, 1.0)]
    
    try:
        doc = fitz.open(pdf_path)
        if page_number >= len(doc):
            logger.warning(f"Page number {page_number} out of range for {pdf_path}, max page: {len(doc)-1}")
            doc.close()
            return [(0.0, 1.0)]
            
        page = doc[page_number]
        page_height = page.rect.height
        
        # Get text blocks with their positions
        blocks = page.get_text("dict")["blocks"]
        
        # Extract all text lines with their y-positions
        lines = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    y_pos = line["bbox"][1] / page_height  # Normalize to 0-1
                    lines.append((y_pos, line))
        
        # Sort by vertical position
        lines.sort(key=lambda x: x[0])
        
        # Find large vertical gaps that might indicate separate tables
        gaps = []
        for i in range(1, len(lines)):
            gap_size = lines[i][0] - lines[i-1][0]
            if gap_size > 0.08:  # Significant gap threshold
                gaps.append((lines[i-1][0], lines[i][0]))
        
        # Use the largest gap to identify table boundaries
        if not gaps:
            # No significant gaps found - assume single table
            tables = [(0.0, 1.0)]
        else:
            # Sort gaps by size (largest first)
            gaps.sort(key=lambda x: x[1]-x[0], reverse=True)
            
            # Use the largest gap to separate tables
            main_gap = gaps[0]
            tables = [
                (0.0, main_gap[0] + 0.02),  # Top table (add margin)
                (main_gap[1] - 0.02, 1.0)   # Bottom table (add margin)
            ]
        
        doc.close()
        return tables
    
    except Exception as e:
        logger.error(f"Error detecting tables in {pdf_path}, page {page_number}: {e}")
        return [(0.0, 1.0)]  # Default if error occurs


def is_table_not_caption(text_block):
    """
    Determine if a text block is likely a full table rather than a caption.
    """
    if not text_block:
        return False
        
    lines = text_block.split('\n')
    
    # Tables typically have multiple lines
    if len(lines) < 3:
        return False
    
    # Tables often contain numbers
    numbers_count = len(re.findall(r'\d+', text_block))
    if numbers_count < 5:
        return False
    
    # Check for column-like structure (consistent whitespace patterns)
    spaces = []
    for line in lines[:min(5, len(lines))]:
        # Find positions of spaces
        pos = [i for i, char in enumerate(line) if char.isspace()]
        spaces.append(pos)
    
    # If we have multiple lines with similar space positions, likely a table
    if len(spaces) >= 3:
        # Look for consistent spacing patterns
        common_spaces = set(range(len(max(spaces, key=len))))
        for positions in spaces:
            for i in list(common_spaces):
                if not any(abs(i-p) <= 2 for p in positions):
                    common_spaces.discard(i)
        
        if len(common_spaces) >= 2:  # At least two consistent column separators
            return True
    
    return False


def enrich_table_metadata(input_metadata_path, corrected_toc_path, output_metadata_path, pdf_dirs):
    """Enrich table metadata with improved detection and splitting."""
    # Load metadata and corrected TOC
    metadata = load_json(input_metadata_path)
    corrected_toc = None
    if os.path.exists(corrected_toc_path):
        try:
            corrected_toc = load_json(corrected_toc_path)
            logger.info(f"Loaded corrected TOC from {corrected_toc_path}")
        except Exception as e:
            logger.error(f"Error loading corrected TOC: {e}")
    
    enriched_metadata = []
    
    # Check if pdf_dirs is a string and convert to list if needed
    if isinstance(pdf_dirs, str):
        pdf_dirs = [pdf_dirs]
    
    logger.info(f"Looking for PDFs in directories: {pdf_dirs}")
    
    for i, item in enumerate(metadata):
        title = item.get('title', '')
        logger.info(f"Processing item {i+1}/{len(metadata)}: {title}")
        
        # Clean up the title using corrected TOC
        cleaned_title = clean_title(title, corrected_toc)
        item['original_title'] = title
        item['title'] = cleaned_title
        
        # Initial check if this title *might* contain multiple tables
        might_have_multiple = has_multiple_tables_indicator(cleaned_title)
        
        if might_have_multiple:
            # Try to find the PDF to verify
            pdf_path = find_pdf_for_item(item, pdf_dirs)
            has_multiple_tables = False
            table_positions = []
            
            # PDF-based verification (primary method)
            if pdf_path and os.path.exists(pdf_path) and PYMUPDF_AVAILABLE:
                try:
                    page_number = item.get('pdf_index', 0)
                    logger.info(f"Verifying multiple tables in PDF {pdf_path}, page {page_number}")
                    
                    table_positions = detect_tables_in_page(pdf_path, page_number)
                    has_multiple_tables = len(table_positions) > 1
                    
                    if has_multiple_tables:
                        logger.info(f"PDF verification confirms multiple tables on page {page_number}")
                    else:
                        logger.info(f"PDF verification found only one table on page {page_number}")
                        
                except Exception as e:
                    logger.error(f"Error detecting tables in PDF: {e}")
            
            # If PDF verification confirmed multiple tables or we don't have PDF access
            # and the title strongly suggests multiple tables, proceed with splitting
            if has_multiple_tables or (not pdf_path and might_have_multiple):
                # Split the title
                split_titles = split_table_title(cleaned_title)
                
                # If title splitting produced multiple parts
                if len(split_titles) > 1:
                    logger.info(f"Splitting title into {len(split_titles)} parts: {split_titles}")
                    
                    # If we don't have verified table positions from PDF, create artificial ones
                    if not table_positions or len(table_positions) < len(split_titles):
                        table_count = len(split_titles)
                        height_per_table = 1.0 / table_count
                        table_positions = [(i * height_per_table, (i + 1) * height_per_table) 
                                          for i in range(table_count)]
                    
                    # Create separate items for each split title
                    for j, split_title in enumerate(split_titles):
                        new_item = item.copy()
                        new_item['title'] = split_title
                        new_item['table_position'] = j + 1  # 1-based index
                        new_item['table_count'] = len(split_titles)
                        if pdf_path:
                            new_item['pdf_path'] = pdf_path
                        if j < len(table_positions):
                            new_item['table_vertical_range'] = table_positions[j]
                        new_item['split_from'] = title
                        new_item['split_method'] = 'pdf_verified' if has_multiple_tables else 'title_indicator'
                        enriched_metadata.append(new_item)
                    
                    # Skip adding the original item since we created split items
                    continue
        
        # For single tables or if we decided not to split
        item['table_position'] = 1
        item['table_count'] = 1
        # Record PDF path if found
        pdf_path = find_pdf_for_item(item, pdf_dirs)
        if pdf_path:
            item['pdf_path'] = pdf_path
        enriched_metadata.append(item)
        
        # Check if "unmatched" items are actually tables
        if item.get('status') == 'unmatched' and 'text' in item:
            if is_table_not_caption(item.get('text', '')):
                logger.info(f"Reclassified unmatched item as table: {cleaned_title}")
                item['status'] = 'table'
                item['reclassified'] = True
    
    # Save the enriched metadata
    save_json(enriched_metadata, output_metadata_path)
    logger.info(f"Enriched metadata saved to {output_metadata_path}")
    return enriched_metadata


def main():
    parser = argparse.ArgumentParser(description="Enrich table metadata with improved detection and splitting")
    parser.add_argument("--input", default="data/toc_table_metadata.json", help="Input metadata file")
    parser.add_argument("--corrected-toc", default="data/toc_corrected.json", help="Corrected TOC file")
    parser.add_argument("--output", default="data/toc_table_metadata_enriched.json", help="Output metadata file")
    parser.add_argument("--pdf-dir", default="data/original", help="Directory containing PDF files")
    parser.add_argument("--additional-pdf-dirs", nargs="*", default=[], help="Additional directories to check for PDFs")
    
    args = parser.parse_args()
    
    if not PYMUPDF_AVAILABLE:
        logger.warning("For full functionality, please install PyMuPDF: pip install pymupdf")
    
    # Combine primary and additional PDF directories
    pdf_dirs = [args.pdf_dir] + args.additional_pdf_dirs
    
    enrich_table_metadata(args.input, args.corrected_toc, args.output, pdf_dirs)


if __name__ == "__main__":
    main()