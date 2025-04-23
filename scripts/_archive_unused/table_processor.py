from pathlib import Path
import pdfplumber
from typing import List
from base_processor import BaseProcessor
from utils import list_pdfs, save_dataframe, clean_filename
from processors import parse_table_from_text, clean_table


class TableProcessor(BaseProcessor):
    def run(self):
        pdf_files = list_pdfs(self.input_path)
        for pdf_path in pdf_files:
            print(f"Processing {pdf_path.name}...")
            data = self.extract_text(pdf_path)
            df = parse_table_from_text(data)
            df = clean_table(df)
            output_file = self.output_path / f"{clean_filename(pdf_path.stem)}.csv"
            save_dataframe(df, output_file)

    def extract_text(self, pdf_path: Path) -> List[str]:
        """Extracts text lines from a PDF file using pdfplumber."""
        lines = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines.extend(text.splitlines())
        return lines
