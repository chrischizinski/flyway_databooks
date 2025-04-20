import re
import json
import argparse
from pathlib import Path
from difflib import SequenceMatcher
from pdfminer.high_level import extract_text

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "original" / "central_flyway_databook_2023.pdf"
DEFAULT_TOC_PATH = ROOT / "data" / "toc_flat.json"
DEFAULT_OUT_PATH = ROOT / "data" / "toc_table_metadata.json"

# Parse command line arguments
parser = argparse.ArgumentParser(description="Verify TOC entries against page captions")
parser.add_argument("--input", type=str, help="Path to input TOC JSON file", default=str(DEFAULT_TOC_PATH))
parser.add_argument("--output", type=str, help="Path to output metadata JSON file", default=str(DEFAULT_OUT_PATH))
parser.add_argument("--pdf", type=str, help="Path to PDF file", default=str(PDF_PATH))
args = parser.parse_args()

TOC_PATH = Path(args.input)
OUT_PATH = Path(args.output)
PDF_PATH = Path(args.pdf)

STOP_WORDS = {"and", "the", "of", "in", "on", "to", "for"}
SPLIT_REGEX = r"\band\b|,"


def normalize(text):
    text = text.lower()
    text = re.sub(r"[()\[\]{}:.,\-]", "", text)
    tokens = [t for t in text.split() if t not in STOP_WORDS]
    return " ".join(tokens)


def fuzzy_match(toc_term, captions):
    toc_norm = normalize(toc_term)
    best_score = 0
    best_match = None
    for caption in captions:
        cap_norm = normalize(caption)
        score = SequenceMatcher(None, toc_norm, cap_norm).ratio()

        # Add boost if TOC term is a substring of the caption
        if toc_norm in cap_norm:
            score += 0.15
        elif any(word in cap_norm for word in toc_norm.split()):
            score += 0.05

        if score > best_score:
            best_score = score
            best_match = caption
    return best_match, min(best_score, 1.0)


def detect_page_captions(text):
    lines = text.split("\n")
    candidates = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped.split()) < 2:
            continue
        if sum(c.isupper() for c in stripped) / len(stripped) > 0.4:
            candidates.append(stripped)
    return candidates


def main():
    if not TOC_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {TOC_PATH}")
    
    print(f"🔍 Verifying TOC entries against page captions...")
    print(f"📄 Using TOC file: {TOC_PATH}")
    
    with open(TOC_PATH) as f:
        toc_data = json.load(f)

    results = []

    # Handle different formats of TOC JSON (flat list vs hierarchical)
    if isinstance(toc_data, list):
        # Flat format (list of entries)
        for entry in toc_data:
            title = entry["title"]
            actual_page = entry["page"]
            section = entry.get("section", "")
            
            page_num = actual_page - 1
            page_text = extract_text(PDF_PATH, page_numbers=[page_num])
            detected = detect_page_captions(page_text)
            toc_terms = [t.strip() for t in re.split(SPLIT_REGEX, title) if t.strip()]

            for term in toc_terms:
                matched_caption, score = fuzzy_match(term, detected)
                results.append({
                    "section": section,
                    "toc_entry": title,
                    "term": term,
                    "matched_caption": matched_caption,
                    "match_score": round(score, 3),
                    "page": actual_page
                })
    else:
        # Legacy hierarchical format
        print("⚠️ Warning: Using legacy hierarchical TOC format")
        for section, entries in toc_data.items():
            for title, actual_page in entries.items():
                page_num = actual_page - 1
                page_text = extract_text(PDF_PATH, page_numbers=[page_num])
                detected = detect_page_captions(page_text)
                toc_terms = [t.strip() for t in re.split(SPLIT_REGEX, title) if t.strip()]

                for term in toc_terms:
                    matched_caption, score = fuzzy_match(term, detected)
                    results.append({
                        "section": section,
                        "toc_entry": title,
                        "term": term,
                        "matched_caption": matched_caption,
                        "match_score": round(score, 3),
                        "page": actual_page
                    })

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"✅ TOC verification metadata saved to: {OUT_PATH}")
    print(f"📊 Processed {len(results)} entries from {len(set(r['toc_entry'] for r in results))} TOC items")


if __name__ == "__main__":
    main()
