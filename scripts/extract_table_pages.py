import json
import argparse
from pathlib import Path
from scripts.toc_utils import load_table_metadata
from scripts.row_model import classify_row_ml
from scripts.classify_row_dynamic import clean_rows, is_valid_row
import shutil

TABLES_DIR = Path("tables_extracted")


def slugify(text):
    return (
        text.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="Clear output directory before running")
    args = parser.parse_args()

    if args.clean and TABLES_DIR.exists():
        shutil.rmtree(TABLES_DIR)
        print("\U0001f9f9 Cleared tables_extracted directory")

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    
    toc_path = Path("data/toc_table_metadata.json")
    toc_entries = load_table_metadata(toc_path)
    # Inside `main()` before the loop
    # Right after loading toc_entries
    # Filter entries with a non-empty "rows" list
    valid_entries = [
        entry for entry in toc_entries
        if isinstance(entry, dict) and entry.get("rows")
    ]

    for entry in valid_entries:
        title = entry.get("title", entry.get("caption", "untitled"))
        table_id = entry.get("slug") or slugify(title)
        page = entry["page"]
        
        if "rows" not in entry:
            print(f"⚠️ Skipping: No rows for '{title}' (Page {page})")
            continue
        rows = entry["rows"]

        # Apply ML-based row classification
        labeled = classify_row_ml(rows)

        # Clean rows (remove summary, footnotes, etc.)
        cleaned = clean_rows(labeled)

        # Skip empty or invalid tables
        if not any(is_valid_row(r) for r in cleaned):
            print(f"⚠️ Skipping empty or invalid table: {title}")
            continue

        # Save table
        out_path = TABLES_DIR / f"{table_id}.json"
        with open(out_path, "w") as f:
            json.dump({
                "page": page,
                "title": title,
                "slug": table_id,
                "section": entry.get("section"),
                "caption": entry.get("caption"),
                "headers": entry.get("headers", []),
                "rows": cleaned
            }, f, indent=2)

        print(f"✅ Saved: {out_path.name}")


if __name__ == "__main__":
    main()
