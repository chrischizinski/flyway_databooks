from pdf2image import convert_from_path
from pathlib import Path

# Constants
PDF_PATH = Path("data/original/central_flyway_databook_2023.pdf")
IMAGES_DIR = Path("data/images")
DPI = 300

def convert_pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 300):
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📄 Loading PDF: {pdf_path}")
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    
    for i, page in enumerate(pages, start=1):
        output_path = output_dir / f"page_{i:03}.png"
        page.save(output_path, "PNG")
        print(f"🖼️  Saved: {output_path}")

    print(f"✅ {len(pages)} pages saved as images to {output_dir}")

if __name__ == "__main__":
    convert_pdf_to_images(PDF_PATH, IMAGES_DIR, DPI)