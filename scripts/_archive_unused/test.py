from pdfminer.high_level import extract_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "original" / "central_flyway_databook_2023.pdf"

text = extract_text(PDF_PATH)
print(text[:500])