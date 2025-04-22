#!/usr/bin/env python
# encoding: utf-8

import json
import os
import logging
from pathlib import Path
import argparse
import re

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

def extract_table_from_pdf(pdf_path, page_number, vertical_range=None):
    """
    Extract table content from a PDF page within the specified vertical range.
    
    Args:
        pdf_path (str): Path to the PDF file
        page_number (int): Page number to extract from
        vertical_range (tuple): Optional tuple of (top, bottom) normalized coordinates
        
    Returns:
        dict: Extracted table content with structured representation
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        return None
    
    try:
        doc = fitz.open(pdf_path)
        if page_number >= len(doc):
            logger.error(f"Page number {page_number} out of range for {pdf_path}")
            doc.close()
            return None
        
        page = doc[page_number]
        page_height = page.rect.height
        page_width = page.rect.width
        
        # Define the region to extract
        if vertical_range:
            top, bottom = vertical_range
            clip_rect = fitz.Rect(0, top * page_height, page_width, bottom * page_height)
        else:
            clip_rect = None  # Extract from entire page
        
        # Get text blocks from the region
        blocks = page.get_text("dict", clip=clip_rect)["blocks"]
        
        # Process blocks to identify table structure
        lines = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    y_pos = line["bbox"][1] / page_height  # Normalize y position
                    
                    spans = []
                    for span in line["spans"]:
                        x_pos = span["bbox"][0] / page_width  # Normalize x position
                        spans.append({
                            "text": span["text"],
                            "x_pos": x_pos,
                            "font": span.get("font", ""),
                            "size": span.get("size", 0)
                        })
                    
                    lines.append({
                        "y_pos": y_pos,
                        "spans": spans,
                        "text": " ".join([span["text"] for span in spans])
                    })
        
        # Sort lines by vertical position
        lines.sort(key=lambda x: x["y_pos"])
        
        # Group lines into rows based on y-position proximity
        rows = []
        current_row = []
        last_y = -1
        
        for line in lines:
            if line["text"].strip():  # Skip empty lines
                if last_y == -1 or abs(line["y_pos"] - last_y) < 0.015:  # Threshold for same row
                    current_row.append(line)
                else:
                    if current_row:
                        rows.append(current_row)
                    current_row = [line]
                last_y = line["y_pos"]
        
        if current_row:  # Add the last row
            rows.append(current_row)
        
        # Analyze x-positions across all rows to identify columns
        x_positions = []
        for row in rows:
            for line in row:
                for span in line["spans"]:
                    x_positions.append(span["x_pos"])
        
        # Use clustering to identify column boundaries
        x_positions.sort()
        column_positions = []
        
        if x_positions:
            # Simple column detection based on gaps in x-positions
            gaps = []
            for i in range(1, len(x_positions)):
                gap = x_positions[i] - x_positions[i-1]
                if gap > 0.02:  # Minimum gap for new column
                    gaps.append((gap, (x_positions[i-1] + x_positions[i]) / 2))
            
            # Sort gaps by size (largest first) and take top N
            gaps.sort(reverse=True)
            column_boundaries = [0] + [g[1] for g in gaps[:10]] + [1.0]  # Add start and end
            column_boundaries.sort()
            
            # Clean up boundaries that are too close
            cleaned_boundaries = [column_boundaries[0]]
            for b in column_boundaries[1:]:
                if b - cleaned_boundaries[-1] > 0.05:  # Minimum column width
                    cleaned_boundaries.append(b)
            
            column_positions = cleaned_boundaries
        
        # Now assign spans to columns and create structured table
        structured_rows = []
        
        for row_lines in rows:
            # Initialize with empty cells
            row_data = ["" for _ in range(len(column_positions)-1)]
            
            # Assign spans to columns
            for line in row_lines:
                for span in line["spans"]:
                    # Find which column this span belongs to
                    for i in range(len(column_positions)-1):
                        if column_positions[i] <= span["x_pos"] < column_positions[i+1]:
                            row_data[i] += span["text"] + " "
                            break
            
            # Clean up cells
            row_data = [cell.strip() for cell in row_data]
            structured_rows.append(row_data)
        
        # Result includes both raw text and structured table
        result = {
            "page": page_number,
            "vertical_range": vertical_range,
            "column_count": len(column_positions) - 1,
            "column_positions": column_positions,
            "raw_text": "\n".join([line["text"] for line in lines]),
            "structured_rows": structured_rows
        }
        
        doc.close()
        return result
    
    except Exception as e:
        logger.error(f"Error extracting table from {pdf_path}, page {page_number}: {e}")
        return None

def find_pdf_files(pdf_dir):
    """Find all PDF files in the given directory."""
    pdf_files = []
    for root, _, files in os.walk(pdf_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def match_title_to_pdf(title, pdf_files):
    """Find the best matching PDF for a given table title."""
    # Clean up title for matching
    clean_title = re.sub(r'[^\w\s]', '', title.lower())
    title_words = [word for word in clean_title.split() if len(word) > 3]
    
    best_match = None
    best_score = 0
    
    for pdf_file in pdf_files:
        # Get the filename without directory or extension
        filename = os.path.basename(pdf_file).lower()
        filename = re.sub(r'\.pdf$', '', filename)
        filename = re.sub(r'[^\w\s]', '', filename)
        
        # Count how many significant words from the title are in the filename
        score = sum(1 for word in title_words if word in filename)
        
        # Prefer "databook" or "flyway" in the filename
        if 'databook' in filename or 'flyway' in filename:
            score += 2
            
        if score > best_score:
            best_score = score
            best_match = pdf_file
    
    # If we have *any* PDF and no match was found, return the first one
    if best_match is None and pdf_files:
        logger.info(f"No specific match found for '{title}', using first available PDF")
        return pdf_files[0]
        
    return best_match

def find_potential_page_number(title, pdf_path, item):
    """
    Try to determine the page number for a table.
    
    First check if 'page' or 'pdf_index' exists in the item.
    If not, try to find the page by searching for text similar to the title in the PDF.
    """
    # Check for explicit page information
    if 'pdf_index' in item:
        return item['pdf_index']
    if 'page' in item:
        return item['page'] - 1  # Convert from 1-based to 0-based
    
    # No explicit page info, try to locate by searching the PDF
    try:
        doc = fitz.open(pdf_path)
        
        # Clean up title for searching
        search_title = title.split('(')[0]  # Remove anything in parentheses
        search_title = re.sub(r'[^\w\s]', '', search_title).strip().lower()
        
        # Get first few significant words (3-4) for searching
        search_words = [word for word in search_title.split() if len(word) > 3][:4]
        
        # Try different search strategies
        for search_term in [
            ' '.join(search_words),  # All words
            search_words[0] if search_words else '',  # First word
        ]:
            if not search_term:
                continue
                
            logger.info(f"Searching PDF for: '{search_term}'")
            
            # Search each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text().lower()
                
                # Skip TOC and index pages (typically at the beginning)
                if page_num < 5 and ("contents" in text or "table of contents" in text):
                    continue
                    
                if search_term in text:
                    logger.info(f"Found matching text on page {page_num}")
                    doc.close()
                    return page_num
        
        # If no match found, try searching for the title in TOC
        for page_num in range(min(10, len(doc))):  # Check first 10 pages for TOC
            page = doc[page_num]
            text = page.get_text()
            
            if "contents" in text.lower() or "table of contents" in text.lower():
                # This is likely a TOC page, search for our title
                for line in text.split('\n'):
                    if any(word in line.lower() for word in search_words if word):
                        # Found title in TOC, now extract page number
                        matches = re.search(r'(\d+)\s*$', line)
                        if matches:
                            page_num = int(matches.group(1)) - 1  # Convert to 0-based
                            logger.info(f"Found page number in TOC: {page_num+1}")
                            doc.close()
                            return page_num
        
        # If all else fails, look for sections
        if 'section' in item:
            section = item['section'].lower()
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text().lower()
                
                if section in text:
                    logger.info(f"Found section on page {page_num}")
                    doc.close()
                    return page_num
        
        doc.close()
    except Exception as e:
        logger.error(f"Error searching PDF for page: {e}")
    
    # Default to page 0 if all methods fail
    logger.warning(f"Could not determine page for '{title}', using default page 0")
    return 0

def extract_tables(metadata_path, pdf_dir, output_path, sample_size=5):
    """
    Extract a sample of tables from the metadata.
    
    Args:
        metadata_path (str): Path to enriched metadata JSON
        pdf_dir (str): Directory containing PDF files
        output_path (str): Output path for extracted tables
        sample_size (int): Number of tables to extract for testing
    """
    metadata = load_json(metadata_path)
    logger.info(f"Loaded metadata with {len(metadata)} items")
    
    # Print sample of metadata to understand structure
    if metadata:
        logger.info(f"Sample metadata item: {json.dumps(metadata[0], indent=2)}")
    
    # Print some diagnostic information about the metadata
    statuses = {}
    for item in metadata:
        status = item.get('status', 'unknown')
        statuses[status] = statuses.get(status, 0) + 1
    
    logger.info(f"Status counts: {statuses}")
    
    # Find all PDF files in the directory
    pdf_files = find_pdf_files(pdf_dir)
    logger.info(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    # Take a sample of items to extract
    tables_to_extract = metadata[:min(sample_size, len(metadata))]
    logger.info(f"Selected {len(tables_to_extract)} items for extraction")
    
    # Extract the tables
    extracted_tables = []
    for item in tables_to_extract:
        title = item.get('title', '')
        logger.info(f"Processing item: {title}")
        
        # Find the best matching PDF
        pdf_path = match_title_to_pdf(title, pdf_files)
        
        if not pdf_path:
            logger.warning(f"Could not find a matching PDF for: {title}")
            continue
            
        logger.info(f"Found matching PDF: {pdf_path}")
        
        # Try to determine the page number
        page_number = find_potential_page_number(title, pdf_path, item)
        
        # Get vertical range if specified
        vertical_range = None
        if 'table_vertical_range' in item:
            vertical_range = tuple(item['table_vertical_range'])
        
        logger.info(f"Extracting table: {title} from {pdf_path}, page {page_number}")
        
        try:
            table_content = extract_table_from_pdf(pdf_path, page_number, vertical_range)
            if table_content:
                extracted_table = {
                    "title": title,
                    "section": item.get('section', ''),
                    "page": page_number,
                    "pdf_path": pdf_path,
                    "table_position": item.get('table_position', 1),
                    "content": table_content
                }
                extracted_tables.append(extracted_table)
                logger.info(f"Successfully extracted table: {title}")
            else:
                logger.error(f"Failed to extract table content: {title}")
        except Exception as e:
            logger.error(f"Exception extracting table {title}: {e}")
    
    # Save extracted tables
    save_json(extracted_tables, output_path)
    logger.info(f"Saved {len(extracted_tables)} extracted tables to {output_path}")
    
    return extracted_tables

def main():
    parser = argparse.ArgumentParser(description="Extract table content from PDFs based on metadata")
    parser.add_argument("--metadata", default="data/toc_table_metadata_enriched.json", 
                        help="Path to enriched table metadata")
    parser.add_argument("--pdf-dir", default="data/original", 
                        help="Directory containing PDF files")
    parser.add_argument("--output", default="data/extracted_tables_sample.json", 
                        help="Output path for extracted tables")
    parser.add_argument("--sample-size", type=int, default=5, 
                        help="Number of tables to extract for testing")
    
    args = parser.parse_args()
    
    if not PYMUPDF_AVAILABLE:
        logger.error("PyMuPDF (fitz) is required for table extraction. Install with: pip install pymupdf")
        return
    
    extract_tables(args.metadata, args.pdf_dir, args.output, args.sample_size)

if __name__ == "__main__":
    main()