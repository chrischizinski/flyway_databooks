import argparse
import json
import re
from pathlib import Path
from typing import List, Tuple, Dict

from PIL import Image
import pytesseract
from symspellpy import SymSpell, Verbosity

from .toc_utils import extract_raw_toc_lines, generate_page_mapping

def ocr_toc_pages(start: int, end: int, image_dir: Path) -> str:
   """Concatenate OCR text for a range of TOC pages."""
   full_text = ""
   for i in range(start, end + 1):
       image_path = image_dir / f"page_{i:03d}.png"
       print(f"\n📄 OCR on TOC page: {image_path.name}")
       text = pytesseract.image_to_string(Image.open(image_path))
       full_text += text + "\n"
   return full_text


def setup_symspell(dictionary_path: str) -> SymSpell:
   """Initialize SymSpell from frequency dictionary."""
   sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
   sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)
   return sym_spell


def extract_title_and_page(line: str) -> Tuple[str, int]:
   """
   Extract title and page number from TOC line.
   Accepts any line ending in a number, preceded by dots or spaces.
   """
   match = re.search(r"^(.*?)(?:[\s\.]{3,})(\d{1,3})\s*$", line)
   if match:
       title = match.group(1).strip()
       page = int(match.group(2))
       return title, page
   raise ValueError("No page number found")


def clean_and_correct_toc_entries(raw_lines: List[str], sym_spell: SymSpell) -> List[Tuple[str, int]]:
   """Spellcheck and normalize TOC entries."""
   cleaned_entries = []
   for line in raw_lines:
       try:
           title_raw, page = extract_title_and_page(line)
       except ValueError:
           print(f"⚠️ Skipping line (no page number found): {line}")
           continue

       # Word-by-word spell correction
       corrected = []
       for word in re.findall(r"[A-Za-z@0-9\-']+", title_raw):
           suggestions = sym_spell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
           corrected.append(suggestions[0].term if suggestions else word)

       title = " ".join(corrected).title()
       cleaned_entries.append((title, page))
   return cleaned_entries


def save_json(obj, filename: str):
   with open(filename, "w") as f:
       json.dump(obj, f, indent=2)
   print(f"✅ Saved: {filename}")


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("--toc-start", type=int, required=True)
   parser.add_argument("--toc-end", type=int, required=True)
   parser.add_argument("--first-numbered-page", type=int, required=True)
   parser.add_argument("--first-image-page", type=int, required=True)
   parser.add_argument("--dict", type=str, default="data/symspell/frequency_dictionary_en_82_765.txt")
   parser.add_argument("--image-dir", type=str, default="data/images")
   args = parser.parse_args()

   sym_spell = setup_symspell(args.dict)

   # 1. OCR raw TOC text
   raw_text = ocr_toc_pages(args.toc_start, args.toc_end, Path(args.image_dir))

   # 2. Extract raw lines
   raw_lines = extract_raw_toc_lines(raw_text)

   # 3. Clean and spell-correct
   cleaned_toc = clean_and_correct_toc_entries(raw_lines, sym_spell)

   # 4. Page mapping logic
   toc_map = generate_page_mapping(cleaned_toc, args.first_numbered_page, args.first_image_page)
   offset = args.first_image_page - args.first_numbered_page
   print(f"\n🔢 Estimated offset between logical and actual page numbers: {offset}")

   # 5. Save both TOC and map
   save_json(dict(cleaned_toc), "toc_cleaned.json")
   save_json(toc_map, "toc_image_mapping.json")


if __name__ == "__main__":
   main()