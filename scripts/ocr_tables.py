import os
from pathlib import Path
from PIL import Image
import pytesseract
import pandas as pd
import re

# Set paths
TABLES_RAW_DIR = Path("data/tables_raw")
TABLES_OCR_DIR = Path("data/tables_ocr")
TABLES_OCR_DIR.mkdir(parents=True, exist_ok=True)

def clean_line(line):
    # Normalize spacing and remove stray characters
    line = re.sub(r'[^\x00-\x7F]+', '', line)  # remove non-ASCII
    line = re.sub(r'\s{2,}', '\t', line.strip())  # normalize spacing with tab
    return line

def ocr_table_image(image_path: Path):
    print(f"🔍 OCR-ing: {image_path.name}")
    image = Image.open(image_path)
    raw_text = pytesseract.image_to_string(image, config='--psm 6')  # Assume uniform block of text
    lines = raw_text.splitlines()

    # Clean and structure into rows
    rows = []
    for line in lines:
        cleaned = clean_line(line)
        if cleaned:
            row = cleaned.split('\t')
            rows.append(row)
    return rows

def write_csv(rows, out_path: Path):
    try:
        df = pd.DataFrame(rows)
        df.to_csv(out_path, index=False, header=False)
        print(f"✅ Saved: {out_path.name}")
    except Exception as e:
        print(f"❌ Failed saving {out_path.name}: {e}")

def run_ocr_batch():
    print("📂 Scanning for table images...")
    for img_path in sorted(TABLES_RAW_DIR.glob("*")):
        if img_path.suffix.lower() not in [".png", ".jpg", ".jpeg"]:
            continue
        try:
            rows = ocr_table_image(img_path)
            output_csv = TABLES_OCR_DIR / f"{img_path.stem}.csv"
            write_csv(rows, output_csv)
        except Exception as e:
            print(f"⚠️ Error processing {img_path.name}: {e}")

if __name__ == "__main__":
    run_ocr_batch()