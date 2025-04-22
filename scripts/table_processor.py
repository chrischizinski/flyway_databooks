#!/usr/bin/env python
# encoding: utf-8

from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
import os
import logging
import re

from config import setup_logging, PYMUPDF_AVAILABLE
from utils import load_json, save_json, is_table_row, create_table_schema

# Initialize logger
logger = setup_logging()

if PYMUPDF_AVAILABLE:
    import fitz
else:
    logger.warning("PyMuPDF not found. Install with: pip install pymupdf")

class BaseTableProcessor:
    """Base class for table processing operations."""
    
    def __init__(self, 
                 pdf_path: Optional[Union[str, Path]] = None,
                 output_path: Optional[Union[str, Path]] = None,
                 metadata_path: Optional[Union[str, Path]] = None):
        """
        Initialize the table processor.
        
        Args:
            pdf_path: Path to the PDF file
            output_path: Path to save processed output
            metadata_path: Path to table metadata
        """
        self.pdf_path = Path(pdf_path) if pdf_path else None
        self.output_path = Path(output_path) if output_path else None
        self.metadata_path = Path(metadata_path) if metadata_path else None
        self.metadata = None
        
        if self.pdf_path and not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")
            
        if self.metadata_path and self.metadata_path.exists():
            try:
                self.metadata = load_json(self.metadata_path)
                logger.info(f"Loaded metadata from {self.metadata_path}")
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
        
    def extract_text_from_page(self, page_number: int) -> str:
        """
        Extract text from a PDF page.
        
        Args:
            page_number: Zero-based page number
            
        Returns:
            str: Extracted text
        """
        if not self.pdf_path:
            raise ValueError("PDF path not set")
            
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF is required for text extraction")
            
        try:
            doc = fitz.open(self.pdf_path)
            if page_number >= len(doc):
                raise ValueError(f"Page number {page_number} out of range")
                
            page = doc[page_number]
            text = page.get_text()
            doc.close()
            return text
        except Exception as e:
            logger.error(f"Error extracting text from page {page_number}: {e}")
            return ""
    
    def extract_table_data(self, page_text: str) -> List[List[str]]:
        """
        Extract tabular data from page text.
        
        Args:
            page_text: Text extracted from a PDF page
            
        Returns:
            List of rows, each containing a list of column values
        """
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
    
    def process(self) -> Any:
        """
        Process the tables. To be implemented by subclasses.
        
        Returns:
            Processed data
        """
        raise NotImplementedError("Subclasses must implement process()")
        
    def save(self, data: Any) -> None:
        """
        Save processed data.
        
        Args:
            data: Data to save
        """
        if not self.output_path:
            logger.warning("No output path specified, skipping save")
            return
            
        save_json(data, self.output_path)
        
    def run(self) -> Any:
        """
        Run the full processing pipeline.
        
        Returns:
            Processed data
        """
        data = self.process()
        if data and self.output_path:
            self.save(data)
        return data

class PDFTableExtractor(BaseTableProcessor):
    """Extract tables from PDF based on metadata."""
    
    def __init__(self, 
                 pdf_path: Union[str, Path],
                 metadata_path: Union[str, Path],
                 output_path: Union[str, Path],
                 sample_size: Optional[int] = None):
        """
        Initialize the table extractor.
        
        Args:
            pdf_path: Path to the PDF file
            metadata_path: Path to table metadata
            output_path: Path to save extracted tables
            sample_size: Number of tables to extract (for testing)
        """
        super().__init__(pdf_path, output_path, metadata_path)
        self.sample_size = sample_size
        
    def detect_tables_in_page(self, page_number: int, vertical_range: Optional[Tuple[float, float]] = None):
        """
        Analyze PDF page to detect tables and their positions.
        
        Args:
            page_number: Zero-based page number
            vertical_range: Optional tuple of (top, bottom) normalized coordinates
            
        Returns:
            List of table positions as (top, bottom) vertical coordinates
        """
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF not available - assuming single table per page")
            return [(0.0, 1.0)]
            
        try:
            doc = fitz.open(self.pdf_path)
            if page_number >= len(doc):
                logger.warning(f"Page number {page_number} out of range, max page: {len(doc)-1}")
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
            logger.error(f"Error detecting tables in {self.pdf_path}, page {page_number}: {e}")
            return [(0.0, 1.0)]  # Default if error occurs
    
    def extract_table_from_page(self, page_number: int, vertical_range: Optional[Tuple[float, float]] = None):
        """
        Extract a table from a specific page and vertical range.
        
        Args:
            page_number: Zero-based page number
            vertical_range: Optional tuple of (top, bottom) normalized coordinates
            
        Returns:
            Dict with extracted table data
        """
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF not available - using simple text extraction")
            page_text = self.extract_text_from_page(page_number)
            rows = self.extract_table_data(page_text)
            
            return {
                "page": page_number,
                "vertical_range": vertical_range,
                "structured_rows": rows,
                "raw_text": page_text
            }
        
        try:
            doc = fitz.open(self.pdf_path)
            if page_number >= len(doc):
                logger.error(f"Page number {page_number} out of range")
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
            logger.error(f"Error extracting table from {self.pdf_path}, page {page_number}: {e}")
            return None
    
    def process(self):
        """
        Process tables based on metadata.
        
        Returns:
            List of extracted tables
        """
        if not self.metadata:
            logger.error("No metadata available")
            return []
            
        # Take a sample if specified
        items_to_process = self.metadata
        if self.sample_size and self.sample_size < len(self.metadata):
            items_to_process = self.metadata[:self.sample_size]
            
        logger.info(f"Processing {len(items_to_process)} tables")
        
        extracted_tables = []
        for i, item in enumerate(items_to_process):
            title = item.get('title', '')
            logger.info(f"Processing table {i+1}/{len(items_to_process)}: {title}")
            
            # Determine page number
            page_number = None
            if 'pdf_index' in item:
                page_number = item['pdf_index']
            elif 'page' in item:
                page_number = item['page'] - 1  # Convert from 1-based to 0-based
                
            if page_number is None:
                logger.warning(f"No page number found for {title}")
                continue
                
            # Get vertical range if specified
            vertical_range = None
            if 'table_vertical_range' in item:
                vertical_range = tuple(item['table_vertical_range'])
                
            # Extract the table
            table_content = self.extract_table_from_page(page_number, vertical_range)
            
            if table_content:
                extracted_table = {
                    "title": title,
                    "section": item.get('section', ''),
                    "page": page_number,
                    "pdf_path": str(self.pdf_path),
                    "table_position": item.get('table_position', 1),
                    "content": table_content
                }
                extracted_tables.append(extracted_table)
                logger.info(f"Successfully extracted table: {title}")
            else:
                logger.error(f"Failed to extract table: {title}")
                
        return extracted_tables

class TableMetadataEnricher(BaseTableProcessor):
    """Enrich table metadata with improved detection and splitting."""
    
    def __init__(self, 
                 input_metadata_path: Union[str, Path],
                 corrected_toc_path: Union[str, Path],
                 output_metadata_path: Union[str, Path],
                 pdf_dirs: Union[str, Path, List[Union[str, Path]]]):
        """
        Initialize the metadata enricher.
        
        Args:
            input_metadata_path: Path to input metadata
            corrected_toc_path: Path to corrected TOC
            output_metadata_path: Path to save enriched metadata
            pdf_dirs: Directory or list of directories containing PDFs
        """
        super().__init__(None, output_metadata_path, input_metadata_path)
        self.corrected_toc_path = Path(corrected_toc_path)
        self.pdf_dirs = [pdf_dirs] if isinstance(pdf_dirs, (str, Path)) else pdf_dirs
        self.pdf_dirs = [Path(p) for p in self.pdf_dirs]
        
        # Load corrected TOC if available
        self.corrected_toc = None
        if self.corrected_toc_path.exists():
            try:
                self.corrected_toc = load_json(self.corrected_toc_path)
                logger.info(f"Loaded corrected TOC from {self.corrected_toc_path}")
            except Exception as e:
                logger.error(f"Error loading corrected TOC: {e}")
                
    def has_multiple_tables_indicator(self, title: str) -> bool:
        """
        Check if a title might indicate multiple tables.
        
        Args:
            title: The table title
            
        Returns:
            bool: True if the title might indicate multiple tables
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
        
    def split_table_title(self, title: str) -> List[str]:
        """
        Split a title that contains multiple table references.
        
        Args:
            title: The table title
            
        Returns:
            List of split titles
        """
        if ' and ' in title.lower():
            parts = re.split(r'\s+and\s+', title, flags=re.IGNORECASE)
            return [part.strip() for part in parts]
        elif ',' in title:
            return [part.strip() for part in title.split(',')]
        return [title]  # Return original if no split is possible
        
    def find_pdf_for_item(self, item: Dict, pdf_dirs: List[Path]) -> Optional[Path]:
        """
        Attempt to find the PDF file for an item.
        
        Args:
            item: The metadata item
            pdf_dirs: List of directories to check for PDFs
            
        Returns:
            Path to the PDF if found, None otherwise
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
                    import glob
                    if '*' in pdf_name:
                        matching_files = glob.glob(str(pdf_dir / pdf_name))
                        if matching_files:
                            return Path(matching_files[0])
                    else:
                        pdf_path = pdf_dir / pdf_name
                        if pdf_path.exists():
                            return pdf_path
        
        # Check for explicit filename
        if 'file_name' in item and item['file_name']:
            file_name = item['file_name']
            for pdf_dir in pdf_dirs:
                pdf_path = pdf_dir / file_name
                if pdf_path.exists():
                    return pdf_path
        
        # Check for explicit path
        if 'path' in item and item['path']:
            path = Path(item['path'])
            if path.exists():
                return path
        
        # No PDF found
        return None
        
    def is_table_not_caption(self, text_block: str) -> bool:
        """
        Determine if a text block is likely a full table rather than a caption.
        
        Args:
            text_block: Text to analyze
            
        Returns:
            bool: True if the text appears to be a table
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
        
    def process(self) -> List[Dict]:
        """
        Process the metadata to enrich it.
        
        Returns:
            List of enriched metadata items
        """
        if not self.metadata:
            logger.error("No metadata to process")
            return []
            
        enriched_metadata = []
        
        logger.info(f"Looking for PDFs in directories: {self.pdf_dirs}")
        
        for i, item in enumerate(self.metadata):
            title = item.get('title', '')
            logger.info(f"Processing item {i+1}/{len(self.metadata)}: {title}")
            
            # Clean up the title using corrected TOC
            cleaned_title = clean_title(title, self.corrected_toc)
            item['original_title'] = title
            item['title'] = cleaned_title
            
            # Initial check if this title *might* contain multiple tables
            might_have_multiple = self.has_multiple_tables_indicator(cleaned_title)
            
            if might_have_multiple:
                # Try to find the PDF to verify
                pdf_path = self.find_pdf_for_item(item, self.pdf_dirs)
                has_multiple_tables = False
                table_positions = []
                
                # PDF-based verification (primary method)
                if pdf_path and PYMUPDF_AVAILABLE:
                    try:
                        page_number = item.get('pdf_index', 0)
                        logger.info(f"Verifying multiple tables in PDF {pdf_path}, page {page_number}")
                        
                        # Create a temporary extractor to use its table detection method 
                        temp_extractor = PDFTableExtractor(str(pdf_path), None, None)
                        table_positions = temp_extractor.detect_tables_in_page(page_number)
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
                    split_titles = self.split_table_title(cleaned_title)
                    
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
                                new_item['pdf_path'] = str(pdf_path)
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
            pdf_path = self.find_pdf_for_item(item, self.pdf_dirs)
            if pdf_path:
                item['pdf_path'] = str(pdf_path)
            enriched_metadata.append(item)
            
            # Check if "unmatched" items are actually tables
            if item.get('status') == 'unmatched' and 'text' in item:
                if self.is_table_not_caption(item.get('text', '')):
                    logger.info(f"Reclassified unmatched item as table: {cleaned_title}")
                    item['status'] = 'table'
                    item['reclassified'] = True
        
        return enriched_metadata

class RowClassifier:
    """Classify table rows as headers, data, summary, or footnotes."""
    
    def __init__(self, model_path: Optional[Union[str, Path]] = None, 
                 scaler_path: Optional[Union[str, Path]] = None,
                 labels_path: Optional[Union[str, Path]] = None):
        """
        Initialize the row classifier.
        
        Args:
            model_path: Path to the trained model
            scaler_path: Path to the feature scaler
            labels_path: Path to the label mapping
        """
        self.model = None
        self.scaler = None
        self.labels = None
        
        # Try to load model if paths provided
        if model_path and scaler_path and labels_path:
            try:
                import joblib
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                with open(labels_path) as f:
                    self.labels = json.load(f)
                logger.info("Loaded ML classifier model")
            except Exception as e:
                logger.error(f"Error loading ML model: {e}")
        
        # Keywords for rule-based classification
        self.summary_keywords = {
            'total', 'mean', 'average', 'median', 'subtotal', 'sum',
            'overall', 'all', 'combined', 'pooled', 'grand', 'max'
        }
        
        self.footnote_patterns = [
            r'^\d+\s+[\w\s]', r'^\*\s+', r'^note:', r'^source:',
            r'^data', r'^excludes', r'^includes'
        ]
    
    def extract_features(self, row: List[str]) -> Dict[str, Union[int, float]]:
        """
        Extract features from a row.
        
        Args:
            row: List of cell values
            
        Returns:
            Dictionary of features
        """
        tokens = [cell.strip() for cell in row if cell.strip()]
        num_tokens = len(tokens)
        numeric_tokens = sum(is_numeric(tok) for tok in tokens)
        pct_numeric = numeric_tokens / num_tokens if num_tokens > 0 else 0
        upper_tokens = sum(tok.isupper() for tok in tokens)

        row_text = " ".join(tokens)

        features = {
            "starts_with_year": int(is_year(tokens[0]) if tokens else False),
            "has_summary_keyword": int(any(kw in row_text.lower() for kw in self.summary_keywords)),
            "has_footnote": int(any(re.search(pat, row_text.lower()) for pat in self.footnote_patterns)),
            "num_tokens": num_tokens,
            "num_numeric": numeric_tokens,
            "pct_numeric": pct_numeric,
            "upper_ratio": upper_tokens / num_tokens if num_tokens > 0 else 0
        }

        return features
    
    def classify_row_ml(self, row: List[str]) -> str:
        """
        Classify a row using ML model if available, fall back to rule-based.
        
        Args:
            row: List of cell values
            
        Returns:
            Classification label (header, data, summary, footnote)
        """
        if not self.model or not self.scaler or not self.labels:
            return self.classify_row_rule_based(row)
            
        try:
            import numpy as np
            features = self.extract_features(row)
            feature_names = [
                "starts_with_year", "has_summary_keyword", "has_footnote",
                "num_tokens", "num_numeric", "pct_numeric", "upper_ratio"
            ]
            X = np.array([[features[f] for f in feature_names]])
            X_scaled = self.scaler.transform(X)
            label_index = self.model.predict(X_scaled)[0]
            return self.labels[label_index]
        except Exception as e:
            logger.error(f"Error in ML classification: {e}")
            return self.classify_row_rule_based(row)
    
    def classify_row_rule_based(self, row: List[str], row_index: int = 0, total_rows: int = 0) -> str:
        """
        Classify a row using rule-based heuristics.
        
        Args:
            row: List of cell values
            row_index: Index of the row in the table
            total_rows: Total number of rows in the table
            
        Returns:
            Classification label (header, data, summary, footnote)
        """
        if not row:
            return "unknown"
            
        row_text = " ".join(row).lower()
        
        # Check for header
        if row_index == 0 or (row_index <= 2 and sum(cell.isupper() for cell in row) > len(row) / 2):
            return "header"
            
        # Check for summary
        for keyword in self.summary_keywords:
            if keyword in row_text:
                return "summary"
                
        # Check for footnote
        for pattern in self.footnote_patterns:
            if re.search(pattern, row_text):
                return "footnote"
                
        # Check for footnote position (typically at the end)
        if total_rows > 0 and row_index >= total_rows - 3:
            # Last few rows - check if they contain less numeric content
            numeric_chars = sum(c.isdigit() for c in row_text)
            if numeric_chars < len(row_text) * 0.3:  # Less than 30% numeric
                return "footnote"
                
        # Default to data
        return "data"
    
    def classify_rows(self, rows: List[List[str]]) -> List[Dict]:
        """
        Classify all rows in a table.
        
        Args:
            rows: List of rows, each containing a list of cell values
            
        Returns:
            List of dictionaries with row data and classification
        """
        classified_rows = []
        total_rows = len(rows)
        
        for i, row in enumerate(rows):
            # Try ML classification first, fall back to rule-based
            label = self.classify_row_ml(row)
            
            classified_rows.append({
                "cells": row,
                "label": label,
                "row_index": i,
                "total_rows": total_rows
            })
            
        return classified_rows

class DatabaseWriter:
    """Write extracted tables to a SQLite database."""
    
    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize the database writer.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        
        # Create parent directories if they don't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
    def clean_database(self):
        """Remove existing tables from the database."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Drop all tables except sqlite_sequence
        for table in tables:
            if table[0] != 'sqlite_sequence':
                cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
        
        conn.commit()
        conn.close()
        logger.info(f"Cleaned existing tables from the database")
        
    def create_tables_index(self, conn):
        """
        Create or update the tables index.
        
        Args:
            conn: SQLite connection
        """
        cursor = conn.cursor()
        
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
        
    def add_to_tables_index(self, conn, table_name, page, title, section, footnotes=None):
        """
        Add a table to the tables index.
        
        Args:
            conn: SQLite connection
            table_name: Name of the table
            page: Page number
            title: Table title
            section: Section
            footnotes: Optional footnotes
        """
        cursor = conn.cursor()
        footnotes_json = json.dumps(footnotes) if footnotes else None
        cursor.execute('''
        INSERT INTO table_index (table_name, page_number, title, section, footnotes)
        VALUES (?, ?, ?, ?, ?)
        ''', (table_name, page, title, section, footnotes_json))
        
    def insert_data_into_table(self, conn, table_name, column_names, rows):
        """
        Insert data rows into the table.
        
        Args:
            conn: SQLite connection
            table_name: Name of the table
            column_names: List of column names
            rows: List of data rows
        """
        cursor = conn.cursor()
        
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
            
    def write_table_to_db(self, conn, title, section, page, rows, classified_rows=None):
        """
        Write a table to the database.
        
        Args:
            conn: SQLite connection
            title: Table title
            section: Section
            page: Page number
            rows: Table rows
            classified_rows: Optional classified rows with labels
            
        Returns:
            Table name
        """
        # Create a slug for the table name
        prefix = "flyway_"
        table_slug = slugify(title)
        table_name = f"{prefix}{table_slug}"
        
        # Ensure the table name is not too long for SQLite
        if len(table_name) > 50:
            table_name = f"{prefix}table_page_{page}"
            
        logger.info(f"Processing table: {title}")
        
        if classified_rows:
            # Extract header rows, data rows, and footnotes
            headers = [r["cells"] for r in classified_rows if r["label"] == "header"]
            headers = headers[0] if headers else []
            
            data_rows = [r["cells"] for r in classified_rows if r["label"] == "data"]
            footnotes = [r["cells"] for r in classified_rows if r["label"] == "footnote"]
        else:
            # Simple approach - use first row as header
            headers = rows[0] if rows else []
            data_rows = rows[1:] if rows else []
            footnotes = []
        
        # Create table schema
        schema, column_names = create_table_schema(table_name, headers, data_rows)
        
        # Create the table
        cursor = conn.cursor()
        cursor.execute(schema)
        
        # Insert data
        self.insert_data_into_table(conn, table_name, column_names, data_rows)
        
        # Add to tables index
        self.add_to_tables_index(conn, table_name, page, title, section, footnotes)
        
        return table_name
        
    def write_tables(self, tables, clean_first=False):
        """
        Write multiple tables to the database.
        
        Args:
            tables: List of table dictionaries
            clean_first: Whether to clean the database first
            
        Returns:
            List of written table names
        """
        import sqlite3
        
        # Connect to database
        conn = sqlite3.connect(self.db_path)
        
        # Clean database if requested
        if clean_first:
            self.clean_database()
        
        # Create tables index
        self.create_tables_index(conn)
        
        # Process each table
        table_names = []
        for table in tables:
            title = table.get('title', '')
            section = table.get('section', '')
            page = table.get('page', 0)
            
            # Get rows from table content
            content = table.get('content', {})
            rows = content.get('structured_rows', [])
            
            # Check if we have classified rows
            classified_rows = table.get('classified_rows', None)
            
            # Write to database
            table_name = self.write_table_to_db(conn, title, section, page, rows, classified_rows)
            table_names.append(table_name)
        
        # Commit and close
        conn.commit()
        conn.close()
        
        return table_names

def main():
    """Script to demonstrate the optimized workflow."""
    import argparse
    from config import (
        PDF_PATH, TOC_METADATA_PATH, TOC_ENRICHED_PATH, EXTRACTED_TABLES_PATH,
        ORIGINAL_DATA_DIR, MODEL_PATH, SCALER_PATH, LABELS_PATH, DB_PATH
    )
    
    parser = argparse.ArgumentParser(description="Process tables from PDFs")
    parser.add_argument("--action", choices=["extract", "enrich", "database", "all"], 
                        default="all", help="Action to perform")
    parser.add_argument("--pdf", type=str, default=str(PDF_PATH), 
                        help="Path to the PDF file")
    parser.add_argument("--metadata", type=str, default=str(TOC_METADATA_PATH), 
                        help="Path to the TOC metadata file")
    parser.add_argument("--enriched", type=str, default=str(TOC_ENRICHED_PATH), 
                        help="Path to enriched metadata")
    parser.add_argument("--output", type=str, default=str(EXTRACTED_TABLES_PATH), 
                        help="Path to extracted tables")
    parser.add_argument("--db", type=str, default=str(DB_PATH), 
                        help="Path to database")
    parser.add_argument("--clean", action="store_true", 
                        help="Clean database before writing")
    parser.add_argument("--sample", type=int, default=None, 
                        help="Number of tables to sample")
    
    args = parser.parse_args()
    
    # Perform the requested action(s)
    if args.action in ["enrich", "all"]:
        logger.info("Enriching metadata...")
        enricher = TableMetadataEnricher(
            args.metadata,
            TOC_CORRECTED_PATH,
            args.enriched,
            ORIGINAL_DATA_DIR
        )
        enriched_metadata = enricher.run()
    
    if args.action in ["extract", "all"]:
        logger.info("Extracting tables...")
        extractor = PDFTableExtractor(
            args.pdf,
            args.enriched if args.action in ["all"] else args.metadata,
            args.output,
            args.sample
        )
        extracted_tables = extractor.run()
    
    if args.action in ["database", "all"]:
        logger.info("Writing to database...")
        
        # Load extracted tables if needed
        if args.action != "all":
            extracted_tables = load_json(args.output)
        
        # Initialize row classifier
        classifier = RowClassifier(MODEL_PATH, SCALER_PATH, LABELS_PATH)
        
        # Classify rows in each table
        for table in extracted_tables:
            rows = table.get('content', {}).get('structured_rows', [])
            if rows:
                classified_rows = classifier.classify_rows(rows)
                table['classified_rows'] = classified_rows
        
        # Write to database
        db_writer = DatabaseWriter(args.db)
        table_names = db_writer.write_tables(extracted_tables, args.clean)
        
        logger.info(f"Added {len(table_names)} tables to the database")
    
    logger.info("Done!")

if __name__ == "__main__":
    main()