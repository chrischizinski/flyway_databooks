import json
from pathlib import Path
from scripts.toc_utils import slugify

# Paths
ROOT = Path(__file__).resolve().parents[1]
TOC_PATH = ROOT / "data" / "toc_flat.json"
PAGE_MAPPING_PATH = ROOT / "data" / "toc_page_mapping.json"
OUTPUT_PATH = ROOT / "data" / "toc_table_metadata.json"

def main():
    # Load TOC flat with section info
    with open(TOC_PATH) as f:
        toc_entries = json.load(f)

    # Load mapping from actual PDF page numbers to image page numbers
    with open(PAGE_MAPPING_PATH) as f:
        page_map = json.load(f)

    toc_with_metadata = []
    for entry in toc_entries:
        page = entry["page"]
        actual_page = page_map.get(str(page))  # Map to actual image-based page
        if actual_page is None:
            print(f"⚠️ Page mapping missing for page {page}: {entry['title']}")
            continue

        toc_with_metadata.append({
            "section": entry["section"],
            "title": entry["title"],
            "slug": slugify(entry["title"]),
            "toc_page": page,
            "actual_page": actual_page
        })

    with open(OUTPUT_PATH, "w") as f:
        json.dump(toc_with_metadata, f, indent=2)

    print(f"✅ Saved table metadata to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()