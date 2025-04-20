#!/usr/bin/env python3
"""
Test PDF table extraction on specific pages.

This script extracts table data from specific pages of the PDF
and outputs detailed information for verification against the PDF.
"""

import json
import argparse
import sys
from pathlib import Path
from pdfminer.high_level import extract_text
import re

# Add project root to path to allow imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Now import from scripts
from scripts.row_model import classify_row_ml
from scripts.classify_row import classify_row

# Constants
PDF_PATH = ROOT / "data" / "original" / "central_flyway_databook_2023.pdf"

# Create commandline arguments
parser = argparse.ArgumentParser(description="Test PDF table extraction on specific pages")
parser.add_argument("--pdf", type=str, default=str(PDF_PATH), help="Path to the PDF file")
parser.add_argument("--output", type=str, default="table_extraction_test.json", help="Output JSON file")
args = parser.parse_args()

def is_table_row(line):
    """Check if a line is likely to be part of a table based on patterns."""
    # Check for numeric patterns common in tabular data
    if re.search(r'\d+(\s+\d+){2,}', line):
        return True
    
    # Check for tab or multiple space separation with at least some content (common in tables)
    if re.search(r'[\w\d]+(\s{2,}|\t)[\w\d]+', line):
        return True
    
    return False

def extract_table_data(page_text):
    """Extract tabular data from page text."""
    lines = page_text.split('\n')
    table_lines = []
    
    # Find consecutive lines that look like table rows
    table_section = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if is_table_row(line):
            table_section = True
            table_lines.append(line)
        elif table_section and not is_table_row(line):
            # Check if this might be a header line
            if len(table_lines) < 3:  # Still collecting header rows
                table_lines.append(line)
            else:
                # End of table section
                table_section = False
    
    # Process table lines into rows and columns
    rows = []
    for line in table_lines:
        # Split by whitespace while preserving content
        cols = re.split(r'\s{2,}|\t', line)
        # Remove empty strings and strip whitespace
        cols = [col.strip() for col in cols if col.strip()]
        if cols:
            rows.append(cols)
    
    return rows

def process_rows_with_ml(rows):
    """Process rows with ML classification."""
    processed_rows = []
    
    for i, row in enumerate(rows):
        # Try ML classification first
        try:
            ml_label = classify_row_ml(row)
            processed_rows.append({
                "cells": row,
                "label": ml_label,
                "row_index": i,
                "total_rows": len(rows)
            })
        except Exception as e:
            # Fall back to rule-based classification if ML fails
            rule_label = classify_row(row, i, len(rows))
            processed_rows.append({
                "cells": row, 
                "label": rule_label,
                "row_index": i,
                "total_rows": len(rows)
            })
    
    return processed_rows

def extract_header_rows(labeled_rows):
    """Extract header rows from labeled rows."""
    headers = []
    
    # Get rows labeled as headers
    header_rows = [r["cells"] for r in labeled_rows if r["label"] == "header"]
    
    # If no explicit headers, try to use the first row
    if not header_rows and labeled_rows:
        header_rows = [labeled_rows[0]["cells"]]
    
    # Merge multiple header rows if needed
    if len(header_rows) > 1:
        # Simple concatenation for now
        headers = []
        for i in range(len(header_rows[0])):
            cell_values = []
            for row in header_rows:
                if i < len(row) and row[i].strip():
                    cell_values.append(row[i])
            headers.append(" ".join(cell_values))
    elif header_rows:
        headers = header_rows[0]
    
    return headers

def extract_data_rows(labeled_rows):
    """Extract data rows from labeled rows."""
    return [r["cells"] for r in labeled_rows if r["label"] == "data"]

def extract_footnotes(labeled_rows):
    """Extract footnotes from labeled rows."""
    return [r["cells"] for r in labeled_rows if r["label"] == "footnote"]

def extract_summary_rows(labeled_rows):
    """Extract summary rows from labeled rows."""
    return [r["cells"] for r in labeled_rows if r["label"] == "summary"]

def detect_table_title(page_text):
    """Try to detect the table title from page text."""
    lines = page_text.split('\n')
    potential_titles = []
    
    for line in lines:
        line = line.strip()
        # Look for all-caps lines that might be titles
        if line and line.isupper() and len(line) > 15:
            potential_titles.append(line)
        # Look for lines with specific title patterns
        elif re.search(r'TABLE|FIGURE|APPENDIX', line, re.IGNORECASE):
            potential_titles.append(line)
    
    return potential_titles

def main():
    pdf_path = Path(args.pdf)
    output_path = Path(args.output)
    
    # Test specific pages: page 2 (index 1) and page 6 (index 5) in the PDF
    test_pages = [1, 5]  # 0-indexed
    
    results = {}
    
    for page_index in test_pages:
        page_num = page_index + 1  # 1-indexed for display
        print(f"📄 Processing PDF page {page_num} (index {page_index})...")
        
        try:
            page_text = extract_text(pdf_path, page_numbers=[page_index])
            
            # Try to detect table titles
            potential_titles = detect_table_title(page_text)
            
            # Extract table data
            rows = extract_table_data(page_text)
            
            if not rows:
                print(f"⚠️ No table data found on page {page_num}")
                results[f"page_{page_num}"] = {
                    "error": "No table data found",
                    "page_text": page_text[:500] + "..." if len(page_text) > 500 else page_text,
                    "potential_titles": potential_titles
                }
                continue
            
            # Process rows with ML classification
            labeled_rows = process_rows_with_ml(rows)
            
            # Extract different row types
            headers = extract_header_rows(labeled_rows)
            data_rows = extract_data_rows(labeled_rows)
            footnotes = extract_footnotes(labeled_rows)
            summary_rows = extract_summary_rows(labeled_rows)
            
            # Print detailed information for verification
            print(f"\nPotential Table Titles:")
            for title in potential_titles:
                print(f"  - {title}")
            
            print(f"\nHeaders ({len(headers)}):")
            for i, header in enumerate(headers):
                print(f"  {i+1}. {header}")
            
            print(f"\nData Rows ({len(data_rows)}):")
            for i, row in enumerate(data_rows[:5]):  # First 5 rows only for brevity
                print(f"  {i+1}. {row}")
            if len(data_rows) > 5:
                print(f"  ... ({len(data_rows) - 5} more rows)")
            
            print(f"\nFootnotes ({len(footnotes)}):")
            for i, note in enumerate(footnotes):
                print(f"  {i+1}. {note}")
            
            print(f"\nSummary Rows ({len(summary_rows)}):")
            for i, row in enumerate(summary_rows):
                print(f"  {i+1}. {row}")
            
            # Store all details in results
            results[f"page_{page_num}"] = {
                "potential_titles": potential_titles,
                "headers": headers,
                "data_rows": data_rows,
                "footnotes": footnotes,
                "summary_rows": summary_rows,
                "all_rows": [{"cells": r["cells"], "label": r["label"]} for r in labeled_rows]
            }
            
            print(f"\n✅ Page {page_num} processing complete")
            print("-" * 80)
            
        except Exception as e:
            print(f"❌ Error processing page {page_num}: {e}")
            results[f"page_{page_num}"] = {"error": str(e)}
    
    # Save results to JSON
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_path}")

if __name__ == "__main__":
    main()
