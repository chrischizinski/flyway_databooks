#!/usr/bin/env python
# encoding: utf-8

import json
import os
import logging
import re
from pathlib import Path
import argparse

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

def calculate_page_offset(pdf_path, toc_data):
    """
    Calculate the offset between PDF page indices and printed page numbers
    using the TOC data.
    
    Args:
        pdf_path: Path to the PDF file
        toc_data: Table of contents data with titles and page numbers
    
    Returns:
        int: The calculated offset (printed_page - pdf_index)
    """
    if not toc_data:
        logger.warning("No TOC data available to calculate page offset")
        return 0
        
    # Flatten the TOC data to get all entries
    all_entries = []
    for section, entries in toc_data.items():
        for title, page_num in entries.items():
            all_entries.append((title, page_num))
    
    if not all_entries:
        logger.warning("TOC data has no entries")
        return 0
    
    # Sort by page number
    all_entries.sort(key=lambda x: x[1])
    
    # Try to locate a few entries in the PDF to determine offset
    offsets = []
    try:
        doc = fitz.open(pdf_path)
        
        # Test several entries from different parts of the document
        test_indices = [0, len(all_entries)//4, len(all_entries)//2, 3*len(all_entries)//4, -1]
        test_entries = [all_entries[i] for i in test_indices if 0 <= i < len(all_entries)]
        
        for title, printed_page in test_entries:
            # Clean title for searching
            clean_title = re.sub(r'[^\w\s]', '', title.strip().lower())
            search_words = [word for word in clean_title.split() if len(word) > 3][:3]
            
            if not search_words:
                continue
                
            search_term = ' '.join(search_words)
            
            # Search in a range around the expected page
            expected_pdf_index = printed_page - 1  # Initial guess
            search_range = 10
            
            for i in range(max(0, expected_pdf_index - search_range), 
                           min(len(doc), expected_pdf_index + search_range + 1)):
                text = doc[i].get_text().lower()
                if search_term in text:
                    offset = printed_page - i
                    offsets.append(offset)
                    logger.info(f"Found '{title}' on PDF page {i}, printed page {printed_page}, offset: {offset}")
                    break
        
        doc.close()
    except Exception as e:
        logger.error(f"Error calculating page offset: {e}")
    
    # Determine the most common offset
    if offsets:
        from collections import Counter
        offset_counts = Counter(offsets)
        most_common_offset = offset_counts.most_common(1)[0][0]
        logger.info(f"Calculated page offset: {most_common_offset}")
        return most_common_offset
    
    logger.warning("Could not determine page offset, using default of 1")
    return 1  # Default offset (commonly, PDF page 0 = printed page 1)

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

def find_pdf_for_title(title, toc_data, pdf_files):
    """
    Find the best matching PDF for a given table title using TOC data.
    
    Args:
        title: The table title to find
        toc_data: Dictionary mapping PDF paths to TOC data
        pdf_files: List of available PDF files
    
    Returns:
        Tuple of (pdf_path, page_number, section) or (None, None, None) if not found
    """
    # Clean title for matching
    clean_title = re.sub(r'[^\w\s]', '', title.lower()).strip()
    title_words = clean_title.split()
    
    # Check each TOC to see if this title exists
    for pdf_path, toc in toc_data.items():
        for section, entries in toc.items():
            for toc_title, page_num in entries.items():
                toc_clean = re.sub(r'[^\w\s]', '', toc_title.lower()).strip()
                
                # Check for exact match first
                if clean_title == toc_clean:
                    logger.info(f"Found exact TOC match for '{title}' in {pdf_path}")
                    return pdf_path, page_num, section
                
                # Then check for significant word overlap (80% of words)
                toc_words = toc_clean.split()
                common_words = set(title_words) & set(toc_words)
                if len(common_words) >= 0.8 * len(title_words) and len(common_words) >= 0.8 * len(toc_words):
                    logger.info(f"Found partial TOC match for '{title}' -> '{toc_title}' in {pdf_path}")
                    return pdf_path, page_num, section
    
    # If no match in TOC, try to find the best PDF match by filename keywords
    best_pdf = None
    best_score = 0
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path).lower()
        filename = re.sub(r'\.pdf$', '', filename)
        filename = re.sub(r'[^\w\s]', '', filename)
        
        # Count how many significant words from the title are in the filename
        score = sum(1 for word in title_words if len(word) > 3 and word in filename)
        
        # Prefer "databook" or "flyway" in the filename
        if 'databook' in filename or 'flyway' in filename:
            score += 2
            
        if score > best_score:
            best_score = score
            best_pdf = pdf_path
    
    if best_pdf:
        logger.info(f"Found best matching PDF for '{title}' by filename: {best_pdf}")
        return best_pdf, None, None
    
    # If all else fails, return the first PDF if available
    if pdf_files:
        logger.warning(f"No match found for '{title}', using first available PDF")
        return pdf_files[0], None, None
    
    return None, None, None

def extract_tables(metadata_path, toc_dir, pdf_dir, output_path, sample_size=5):
    """
    Extract tables from PDFs based on metadata and TOC information.
    
    Args:
        metadata_path: Path to the enriched table metadata JSON
        toc_dir: Directory containing extracted TOC JSON files
        pdf_dir: Directory containing PDF files
        output_path: Output path for extracted tables
        sample_size: Number of tables to extract for testing
    """
    metadata = load_json(metadata_path)
    logger.info(f"Loaded metadata with {len(metadata)} items")
    
    # Find all PDF files in the directory
    pdf_files = find_pdf_files(pdf_dir)
    logger.info(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    # Load any available TOC data
    toc_data = {}
    for toc_file in Path(toc_dir).glob("*.json"):
        try:
            toc = load_json(toc_file)
            pdf_name = toc_file.stem
            
            # Try to find matching PDF file
            matching_pdfs = [p for p in pdf_files if os.path.basename(p).lower().startswith(pdf_name.lower())]
            if matching_pdfs:
                toc_data[matching_pdfs[0]] = toc
                logger.info(f"Loaded TOC data for {matching_pdfs[0]}")
        except Exception as e:
            logger.error(f"Error loading TOC file {toc_file}: {e}")
    
    logger.info(f"Loaded TOC data for {len(toc_data)} PDFs")
    
    # Calculate page offsets for each PDF with TOC data
    pdf_page_offsets = {}
    for pdf_path, toc in toc_data.items():
        pdf_page_offsets[pdf_path] = calculate_page_offset(pdf_path, toc)
    
    # Take a sample of items to extract
    tables_to_extract = metadata[:min(sample_size, len(metadata))]
    logger.info(f"Selected {len(tables_to_extract)} items for extraction")
    
    # Extract the tables
    extracted_tables = []
    for item in tables_to_extract:
        title = item.get('title', '')
        logger.info(f"Processing item: {title}")
        
        # Find the matching PDF, page number, and section using TOC
        pdf_path, page_num, section = find_pdf_for_title(title, toc_data, pdf_files)
        
        if not pdf_path:
            logger.warning(f"Could not find a matching PDF for: {title}")
            continue
        
        # Update section if found in TOC
        if section and not item.get('section'):
            item['section'] = section
            
        # Calculate the PDF index from the printed page number
        page_offset = pdf_page_offsets.get(pdf_path, 1)  # Default offset is 1
        
        if page_num is not None:
            # Use page number from TOC
            page_number = page_num - page_offset
            logger.info(f"Using page {page_num} from TOC (PDF index: {page_number})")
        elif 'page' in item:
            # Use page from metadata
            page_number = item['page'] - page_offset
            logger.info(f"Using page {item['page']} from metadata (PDF index: {page_number})")
        elif 'pdf_index' in item:
            # Use pdf_index directly
            page_number = item['pdf_index']
            logger.info(f"Using pdf_index {page_number} from metadata")
        else:
            # Default to page 0
            page_number = 0
            logger.warning(f"No page information available for {title}, using default page 0")
        
        # Ensure page number is valid
        page_number = max(0, page_number)
        
        # Get vertical range if specified
        vertical_range = None
        if 'table_vertical_range' in item:
            vertical_range = tuple(item['table_vertical_range'])
            logger.info(f"Using vertical range: {vertical_range}")
        
        logger.info(f"Extracting table: {title} from {pdf_path}, page {page_number}")
        
        try:
            table_content = extract_table_from_pdf(pdf_path, page_number, vertical_range)
            if table_content:
                extracted_table = {
                    "title": title,
                    "section": item.get('section', ''),
                    "page": page_number,
                    "printed_page": page_number + page_offset if page_offset else None,
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
    parser.add_argument("--toc-dir", default="data/toc", 
                        help="Directory containing extracted TOC JSON files")
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
    
    # Create TOC directory if it doesn't exist
    os.makedirs(args.toc_dir, exist_ok=True)
    
    extract_tables(args.metadata, args.toc_dir, args.pdf_dir, args.output, args.sample_size)

if __name__ == "__main__":
    main()