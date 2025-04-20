import json
import argparse
from pathlib import Path


def sanitize(text):
    return text.replace('\u00a0', ' ').replace('\xa0', ' ').strip()


def flatten_toc(toc):
    flat_list = []
    for section, entries in toc.items():
        for title, page in entries.items():
            flat_list.append({
                "section": sanitize(section),
                "title": sanitize(title),
                "page": page
            })
    return flat_list


def main():
    parser = argparse.ArgumentParser(description="Flatten hierarchical TOC JSON")
    parser.add_argument("--input", type=Path, required=True, help="Path to hierarchical TOC JSON")
    parser.add_argument("--output", type=Path, required=True, help="Path to save flattened TOC JSON")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    with open(args.input, "r") as f:
        toc = json.load(f)

    flat_toc = flatten_toc(toc)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(flat_toc, f, indent=2)

    print(f"✅ Flattened TOC with {len(flat_toc)} entries saved to {args.output}")


if __name__ == "__main__":
    main()