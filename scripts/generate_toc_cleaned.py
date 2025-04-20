import json
import re
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = ROOT / "data" / "toc_flat.json"
DEFAULT_CLEANED_PATH = ROOT / "data" / "toc_cleaned.json"
DEFAULT_METADATA_PATH = ROOT / "data" / "toc_table_metadata.json"

# Parse command line arguments
parser = argparse.ArgumentParser(description="Generate cleaned TOC files for interactive tools")
parser.add_argument("--input", type=str, help="Path to input TOC flat JSON file", 
                    default=str(DEFAULT_INPUT_PATH))
parser.add_argument("--output-cleaned", type=str, help="Path to output cleaned TOC JSON file", 
                    default=str(DEFAULT_CLEANED_PATH))
parser.add_argument("--output-metadata", type=str, help="Path to output TOC metadata JSON file", 
                    default=str(DEFAULT_METADATA_PATH))
args = parser.parse_args()

INPUT_PATH = Path(args.input)
CLEANED_PATH = Path(args.output_cleaned)
METADATA_PATH = Path(args.output_metadata)

def slugify(text):
    """
    Convert text to a URL-friendly slug format:
    - Remove special characters
    - Replace spaces with underscores
    - Convert to lowercase
    """
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "_", text.strip()).lower()

def main():
    print(f"🔄 Generating cleaned TOC files...")
    print(f"📄 Using input file: {INPUT_PATH}")
    
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"❌ Missing input file: {INPUT_PATH}")

    with open(INPUT_PATH) as f:
        toc_flat = json.load(f)

    # Create dictionary for spell-checking tools
    toc_cleaned = {}
    # Create list with additional metadata for other tools
    toc_table_metadata = []

    for entry in toc_flat:
        title = entry["title"]
        page = entry["page"]
        slug = slugify(title)
        # Add to dictionary format (title → page)
        toc_cleaned[title] = page
        # Add to metadata list with additional fields
        toc_table_metadata.append({
            "section": entry.get("section", ""),
            "title": title,
            "page": page,
            "slug": slug
        })

    # Ensure output directories exist
    CLEANED_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write the output files
    with open(CLEANED_PATH, "w") as f:
        json.dump(toc_cleaned, f, indent=2)

    with open(METADATA_PATH, "w") as f:
        json.dump(toc_table_metadata, f, indent=2)

    print(f"✅ Cleaned dictionary format written to: {CLEANED_PATH}")
    print(f"✅ Enhanced metadata format written to: {METADATA_PATH}")
    print(f"📊 Processed {len(toc_cleaned)} TOC entries")

if __name__ == "__main__":
    main()
