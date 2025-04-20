
import json
import re
import argparse
from pathlib import Path


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "_", text.strip()).lower()


def sanitize(text):
    return text.replace('\u00a0', ' ').replace('\xa0', ' ').strip()


def generate_cleaned_outputs(flat_toc):
    toc_cleaned = {}
    toc_table_metadata = []

    for entry in flat_toc:
        title = sanitize(entry["title"])
        section = sanitize(entry.get("section", ""))
        page = entry["page"]
        slug = slugify(title)

        toc_cleaned[title] = page
        toc_table_metadata.append({
            "section": section,
            "title": title,
            "page": page,
            "slug": slug
        })

    return toc_cleaned, toc_table_metadata


def main():
    parser = argparse.ArgumentParser(description="Generate cleaned TOC outputs from flat TOC JSON.")
    parser.add_argument("--input", type=Path, required=True, help="Path to toc_flat.json")
    parser.add_argument("--output-cleaned", type=Path, required=True, help="Path to toc_cleaned.json")
    parser.add_argument("--output-metadata", type=Path, required=True, help="Path to toc_table_metadata.json")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file does not exist: {args.input}")

    with open(args.input) as f:
        flat_toc = json.load(f)

    cleaned_dict, metadata_list = generate_cleaned_outputs(flat_toc)

    args.output_cleaned.parent.mkdir(parents=True, exist_ok=True)
    args.output_metadata.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output_cleaned, "w") as f:
        json.dump(cleaned_dict, f, indent=2)

    with open(args.output_metadata, "w") as f:
        json.dump(metadata_list, f, indent=2)

    print(f"✅ Cleaned dictionary saved to {args.output_cleaned}")
    print(f"✅ Metadata table saved to {args.output_metadata}")
    print(f"📊 {len(cleaned_dict)} entries processed.")


if __name__ == "__main__":
    main()
