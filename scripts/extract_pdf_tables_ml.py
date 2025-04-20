few#!/usr/bin/env python3
"""
Extract tables from PDF and add them to the database with ML row classification.

This script extracts table data directly from the PDF without OCR,
using the table of contents metadata to locate tables and parse their content,
and applies ML-based row classification to identify row types.
"""

import json
import sqlite3
import argparse
from pathlib import Path
from pdfminer.high_level import extract_text
import re
import pandas as pd
from scripts.row_model import classify_row_ml
from scripts.classify_row import classify_row
from scripts.classify_row_dynamic import clean_rows, is_valid_row

# Constants
ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "original" / "central_flyway_databook_2023.pdf"
METADATA_PATH = ROOT / "data" / "toc_table_metadata.json"
DB_PATH = ROOT / "database" / "flyway_data.db"
TABLES_DIR = ROOT / "tables_extracted"

# Create commandline arguments
parser = argparse.ArgumentParser(description="Extract tables from PDF with ML row classification")
parser.add_argument("--pdf", type=str, default=str(PDF_PATH), help="Path to the PDF file")
parser.add_argument("--metadata", type=str, default=str(METADATA_PATH), help="Path to the TOC metadata file")
parser.add_argument("--db", type=str, default=str(DB_PATH), help="Path to the database file")
parser.add_argument("--tables-dir", type=str, default=str(TABLES_DIR), help="Path to tables output directory")
parser.add_argument("--clean", action="store_true", help="Clean existing tables from the database")
parser.add_argument("--save-json", action="store_true", help="Save extracted tables as JSON files")
args = parser.parse_args()

def slugify(text):
    """Convert text to a database-friendly slug."""
    return (
        text.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
        .replace("\u00a0", "_")  # Replace non-breaking spaces
    )

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

def create_table_schema(table_name, headers, data_rows):
    """Create SQL schema for a table based on headers."""
    # Create column names from headers or generate generic ones
    if headers and len(headers) > 0:
        # Clean headers for SQL column names
        column_names = [f'"{slugify(h)}"' for h in headers]
    else:
        # Create generic column names (col1, col2, etc.)
        max_cols = max([len(row) for row in data_rows] or [0])
        column_names = [f'"col{i}"' for i in range(1, max_cols + 1)]
    
    # Create SQL schema
    schema = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    schema += "id INTEGER PRIMARY KEY,\n"
    schema += ",\n".join([f"{col} TEXT" for col in column_names])
    schema += "\n);"
    
    return schema, column_names

def insert_data_into_table(cursor, table_name, column_names, rows):
    """Insert data rows into the table."""
    # Prepare column names for the INSERT statement
    column_str = ", ".join(column_names)
    
    for row in rows:
        # Skip rows that don't match our expected format
        if not row or len(row) < 2:  # At least two columns expected
            continue
            
        # Pad row if it has fewer columns than expected
        while len(row) < len(column_names):
            row.append("")
            
        # Take only as many columns as we have in our schema
        if len(row) > len(column_names):
            row = row[:len(column_names)]
            
        # Escape values for SQL
        values = [value.replace("'", "''") for value in row]
        placeholders = ", ".join(["?" for _ in range(len(values))])
        
        # Insert the row
        query = f"INSERT INTO {table_name} ({column_str}) VALUES ({placeholders})"
        cursor.execute(query, values)

def create_tables_index(cursor):
    """Create or update the tables index."""
    # Create the table_index table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS table_index (
        id INTEGER PRIMARY KEY,
        table_name TEXT,
        page_number INTEGER,
        title TEXT,
        section TEXT,
        footnotes TEXT
    )
    ''')

def add_to_tables_index(cursor, table_name, page, title, section, footnotes=None):
    """Add a table to the tables index."""
    footnotes_json = json.dumps(footnotes) if footnotes else None
    cursor.execute('''
    INSERT INTO table_index (table_name, page_number, title, section, footnotes)
    VALUES (?, ?, ?, ?, ?)
    ''', (table_name, page, title, section, footnotes_json))

def clean_database_tables(conn):
    """Remove existing tables from the database."""
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    # Drop all tables except sqlite_sequence
    for table in tables:
        if table[0] != 'sqlite_sequence':
            cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
    
    conn.commit()
    print(f"🧹 Cleaned existing tables from the database")

def save_table_json(table_data, output_dir, filename):
    """Save table data as JSON file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{filename}.json"
    
    with open(output_path, "w") as f:
        json.dump(table_data, f, indent=2)
    
    print(f"  💾 Saved table JSON: {output_path}")

def main():
    print(f"📊 Extracting tables from PDF: {args.pdf}")
    pdf_path = Path(args.pdf)
    metadata_path = Path(args.metadata)
    db_path = Path(args.db)
    tables_dir = Path(args.tables_dir)
    
    # Make sure output directory exists
    tables_dir.mkdir(parents=True, exist_ok=True)
    
    # Load metadata
    with open(metadata_path) as f:
        metadata = json.load(f)
        
    # Group metadata by page
    pages_metadata = {}
    for entry in metadata:
        page = entry.get('page')
        if page not in pages_metadata:
            pages_metadata[page] = []
        pages_metadata[page].append(entry)
        
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clean database if requested
    if args.clean:
        clean_database_tables(conn)
    
    # Create tables index
    create_tables_index(cursor)
    
    # Counter for tables
    tables_processed = 0
    
    # Process each page with tables
    for page, entries in pages_metadata.items():
        # Extract text from the page
        page_num = page - 1  # PDF page numbers are 0-based
        print(f"📄 Processing page {page}...")
        
        try:
            page_text = extract_text(pdf_path, page_numbers=[page_num])
            
            # Extract table data
            rows = extract_table_data(page_text)
            
            if not rows:
                print(f"⚠️ No table data found on page {page}")
                continue
                
            # Process rows with ML classification
            labeled_rows = process_rows_with_ml(rows)
            
            # Extract header rows, data rows, and footnotes
            headers = extract_header_rows(labeled_rows)
            data_rows = extract_data_rows(labeled_rows)
            footnotes = extract_footnotes(labeled_rows)
            
            if not data_rows:
                print(f"⚠️ No valid data rows found on page {page}")
                continue
            
            # For each table entry on this page
            for entry in entries:
                title = entry.get('toc_entry') or entry.get('matched_caption') or f"Table on page {page}"
                section = entry.get('section', 'Uncategorized')
                
                # Create a slug for the table name
                prefix = "ce_2023_"  # Central Flyway 2023
                table_slug = slugify(title)
                table_name = f"{prefix}{table_slug}"
                
                # Ensure the table name is not too long for SQLite
                if len(table_name) > 50:
                    table_name = f"{prefix}table_page_{page}_{tables_processed}"
                
                print(f"  📋 Processing table: {title}")
                
                # Create table schema
                schema, column_names = create_table_schema(table_name, headers, data_rows)
                
                # Create the table
                cursor.execute(schema)
                
                # Insert data
                insert_data_into_table(cursor, table_name, column_names, data_rows)
                
                # Add to tables index
                add_to_tables_index(cursor, table_name, page, title, section, footnotes)
                
                # Save as JSON if requested
                if args.save_json:
                    table_data = {
                        "page": page,
                        "title": title,
                        "slug": table_slug,
                        "section": section,
                        "headers": headers,
                        "rows": [{'cells': r["cells"], 'label': r["label"]} for r in labeled_rows],
                        "footnotes": footnotes
                    }
                    save_table_json(table_data, tables_dir, table_slug)
                
                tables_processed += 1
                
        except Exception as e:
            print(f"❌ Error processing page {page}: {e}")
    
    # Commit and close
    conn.commit()
    conn.close()
    
    print(f"✅ Added {tables_processed} tables to the database")

if __name__ == "__main__":
    main()
