import re
import json
import argparse
from pathlib import Path
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "original" / "central_flyway_databook_2023.pdf"
OUTPUT_PATH = ROOT / "data" / "toc_hierarchical.json"

PAGE_NUM_RE = re.compile(r"(\d{1,3})\s*$")
SECTION_RE = re.compile(r"^[A-Z\s]+:$")


def parse_toc_lines(lines):
    toc = {}
    current_section = None

    for line in lines:
        text = line.get_text().strip()
        if not text or len(text) < 4:
            continue

        if SECTION_RE.match(text):
            current_section = text.rstrip(": ").title()
            continue

        match = PAGE_NUM_RE.search(text)
        if match:
            page_num = int(match.group(1))
            title = PAGE_NUM_RE.sub("", text).strip()
            if current_section:
                toc.setdefault(current_section, {})[title] = page_num
            else:
                toc.setdefault("Uncategorized", {})[title] = page_num

    return toc


def main():
    parser = argparse.ArgumentParser(description="Extract hierarchical TOC from PDF")
    parser.add_argument("--start", type=int, required=True, help="Start page number (1-based)")
    parser.add_argument("--end", type=int, required=True, help="End page number (1-based)")
    args = parser.parse_args()

    lines = []
    page_range = list(range(args.start - 1, args.end))  # convert to 0-based
    for page_layout in extract_pages(PDF_PATH, page_numbers=page_range):
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                lines.extend(element)

    toc = parse_toc_lines(lines)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(toc, f, indent=2)

    print(f"✅ TOC with hierarchy saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
