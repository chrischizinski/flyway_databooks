#!/usr/bin/env python3
"""
Scan PDF for tables across a range of pages.

This script extracts table data from a range of pages in the PDF
and outputs detailed information to help locate the tables.
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

# Constants
PDF_PATH = ROOT / "data" / "original" / "central_flyway_databook_2023.pdf"

# Create commandline arguments
parser = argparse.ArgumentParser(description="Scan PDF for tables across a range of pages")
parser.add_argument("--pdf", type=str, default=str(PDF_PATH), help="Path to the PDF file")
parser.add_argument("--output", type=str, default="pdf_table_scan.json", help="Output JSON file")
parser.add_argument("--start", type=int, default=1, help="Start page (0-indexed)")
parser.add_argument("--end", type=int, default=15, help="End page (0-indexed)")
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
    
    start_page = args.start
    end_page = args.end
    
    results = {}
    
    print(f"📄 Scanning PDF {pdf_path.name} for tables (pages {start_page}-{end_page})...")
    
    for page_index in range(start_page, end_page + 1):
        print(f"\nPage {page_index}:")
        
        try:
            page_text = extract_text(pdf_path, page_numbers=[page_index])
            
            # Try to detect table titles
            potential_titles = detect_table_title(page_text)
            
            # Extract table data
            rows = extract_table_data(page_text)
            
            # Print summary for this page
            if potential_titles:
                print(f"  📑 Potential Titles: {', '.join(potential_titles[:2])}")
            
            if rows:
                print(f"  📋 Found {len(rows)} potential table rows")
                # Print first few rows as a preview
                for i, row in enumerate(rows[:3]):
                    if i == 0:
                        print(f"  • Header: {' | '.join(row)}")
                    else:
                        print(f"  • Row {i}: {' | '.join(row[:min(3, len(row))])}" + ("..." if len(row) > 3 else ""))
            else:
                print(f"  ❌ No table data detected")
            
            # Store results
            results[f"page_{page_index}"] = {
                "has_table": len(rows) > 0,
                "row_count": len(rows),
                "potential_titles": potential_titles,
                "sample_rows": rows[:5] if rows else [],
                "page_text_preview": page_text[:200].replace("\n", " ") + "..." if page_text else ""
            }
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[f"page_{page_index}"] = {"error": str(e)}
    
    # Save results to JSON
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Scan results saved to: {output_path}")
    
    # Print summary
    pages_with_tables = [page for page, data in results.items() if data.get("has_table", False)]
    print(f"\n📊 Summary: Found potential tables on {len(pages_with_tables)} pages:")
    for page in pages_with_tables:
        page_num = page.split("_")[1]
        row_count = results[page]["row_count"]
        titles = results[page]["potential_titles"]
        title_text = f" - {titles[0]}" if titles else ""
        print(f"  • Page {page_num}: {row_count} rows{title_text}")

if __name__ == "__main__":
    main()
