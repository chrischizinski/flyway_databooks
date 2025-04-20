
import re
import json
import argparse
from pathlib import Path
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer


SECTION_RE = re.compile(r"^[A-Z\s]+:$")
PAGE_NUM_RE = re.compile(r"(\d{1,3})\s*$")


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


def extract_toc(pdf_path: Path, start_page: int, end_page: int):
    lines = []
    try:
        page_range = list(range(start_page - 1, end_page))  # pdfminer is 0-based
        for page_layout in extract_pages(pdf_path, page_numbers=page_range):
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    lines.extend(element)
        return parse_toc_lines(lines)
    except Exception as e:
        raise RuntimeError(f"Failed to extract TOC from PDF: {e}")


def main():
    parser = argparse.ArgumentParser(description="Extract hierarchical TOC from PDF")
    parser.add_argument("--pdf", type=Path, required=True, help="Path to input PDF file")
    parser.add_argument("--start", type=int, required=True, help="Start page number (1-based)")
    parser.add_argument("--end", type=int, required=True, help="End page number (1-based)")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(f"PDF file not found: {args.pdf}")

    toc = extract_toc(args.pdf, args.start, args.end)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(toc, f, indent=2)

    print(f"✅ Extracted TOC saved to {args.output} ({sum(len(v) for v in toc.values())} entries)")


if __name__ == "__main__":
    main()
