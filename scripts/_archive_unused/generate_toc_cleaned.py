import json
import re
from pathlib import Path
from PIL import Image
import pytesseract

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data" / "images"
TOC_OUTPUT = ROOT / "data" / "toc_cleaned.json"

# List of TOC page image files
toc_images = [IMAGE_DIR / f"page_{i:03d}.png" for i in [4, 5]]

def clean_toc_line(line: str) -> str:
    line = re.sub(r"[cseao@S\-\.\:]{8,}", "....", line, flags=re.IGNORECASE)
    line = re.sub(r"\.{2,}", "....", line)
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()

def extract_title_and_last_number(line: str):
    cleaned = clean_toc_line(line)
    numbers = re.findall(r"\d{1,3}", cleaned)
    if numbers:
        page = int(numbers[-1])
        title = re.sub(r"\d{1,3}\s*$", "", cleaned).strip(" .:-")
        return title, page
    raise ValueError("No page number found")

def main():
    toc_entries = {}
    for image_path in toc_images:
        print(f"🧠 OCR: {image_path.name}")
        text = pytesseract.image_to_string(Image.open(image_path))
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                title, page = extract_title_and_last_number(line)
                toc_entries[title] = page
            except ValueError:
                continue

    with open(TOC_OUTPUT, "w") as f:
        json.dump(toc_entries, f, indent=2)
    print(f"\n✅ TOC saved to: {TOC_OUTPUT}")

if __name__ == "__main__":
    main()