#!/usr/bin/env python3
"""
Extract the Migratory Game Bird Hunting Permits table.

This script specifically targets the table on page 8 of the PDF (page 2 by PDF numbering)
with headers YR NF PE NS NB PQ ON MB SK AB BC NT YT NU TOTAL
"""

import json
import sys
from pathlib import Path
from pdfminer.high_level import extract_text
import re
import csv

# Add project root to path to allow imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Constants
PDF_PATH = ROOT / "data" / "original" / "central_flyway_databook_2023.pdf"
PDF_PAGE = 7  # 0-indexed, corresponds to page 8 in the document, page 2 in the PDF

# Expected headers for validation
EXPECTED_HEADERS = ["YR", "NF", "PE", "NS", "NB", "PQ", "ON", "MB", "SK", "AB", "BC", "NT", "YT", "NU", "TOTAL"]

def extract_table_by_columns(page_text):
    """
    Extract table data by trying to align columnar data.
    This approach is better for tables with aligned columns.
    """
    lines = page_text.split('\n')
    table_lines = []
    table_section = False
    header_found = False
    
    # Process the lines to find the table section
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Look for the title
        if "MIGRATORY GAME BIRD HUNTING PERMITS" in line:
            table_section = True
            continue
        
        # Skip until we find the table section
        if not table_section:
            continue
        
        # Try to identify the header line
        if not header_found and any(header in line for header in ["YR", "TOTAL"]):
            header_found = True
            table_lines.append(line)
            continue
        
        # After header is found, collect data rows
        if header_found:
            # Check if it looks like a data row (starts with a year)
            if re.match(r'^\d{4}', line):
                table_lines.append(line)
    
    # Now process the collected lines into a structured table
    rows = []
    for line in table_lines:
        # Simple split based on whitespace, assuming columns are well-aligned
        cols = re.split(r'\s+', line)
        if cols:
            rows.append(cols)
    
    return rows

def is_summary_row(row):
    """Check if a row is a summary row (e.g., average, total)."""
    first_val = row[0].lower() if row else ""
    summary_terms = ["average", "mean", "total", "sum", "median", "max", "min"]
    return any(term in first_val for term in summary_terms)

def validate_headers(headers):
    """Validate the extracted headers against expected headers."""
    # Make both lists lowercase for case-insensitive comparison
    headers_lower = [h.lower() for h in headers]
    expected_lower = [h.lower() for h in EXPECTED_HEADERS]
    
    # Check if all expected headers are present
    return all(exp in headers_lower for exp in expected_lower)

def main():
    # Extract the text from the specific page
    page_text = extract_text(PDF_PATH, page_numbers=[PDF_PAGE])
    
    # Extract the table data
    rows = extract_table_by_columns(page_text)
    
    if not rows:
        print("❌ No table data found")
        return
    
    # The first row should be the headers
    headers = rows[0]
    data_rows = rows[1:]
    
    # Remove summary rows
    data_rows = [row for row in data_rows if not is_summary_row(row)]
    
    # Validate headers
    header_valid = validate_headers(headers)
    
    print(f"📋 Table extraction results:")
    print(f"  • Headers: {' | '.join(headers)}")
    print(f"  • Headers valid: {'✅' if header_valid else '❌'}")
    print(f"  • Data rows found: {len(data_rows)}")
    
    # Print a few sample rows
    print("\n📝 Sample rows:")
    for i, row in enumerate(data_rows[:5]):
        print(f"  {i+1}. {' | '.join(row)}")
    
    # Save results to CSV
    output_csv = "migratory_game_bird_permits.csv"
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data_rows)
    
    print(f"\n💾 Table saved to: {output_csv}")
    
    # Also save as JSON for reference
    output_json = "migratory_game_bird_permits.json"
    with open(output_json, 'w') as f:
        json.dump({
            "title": "MIGRATORY GAME BIRD HUNTING PERMITS BY PROVINCE/TERRITORY OF PURCHASE IN CANADA",
            "headers": headers,
            "data": data_rows
        }, f, indent=2)
    
    print(f"💾 Table also saved as JSON: {output_json}")

if __name__ == "__main__":
    main()
