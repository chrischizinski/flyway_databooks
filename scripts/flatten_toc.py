import json
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]
TOC_CORRECTED = ROOT / "data" / "toc_corrected.json"
TOC_FLAT = ROOT / "data" / "toc_flat.json"


def flatten_toc(toc):
    flat = {}
    for section, entries in toc.items():
        for title, page in entries.items():
            flat[title] = {
                "page": page,
                "section": section
            }
    return flat


def main():
    if not TOC_CORRECTED.exists():
        print(f"❌ TOC corrected file not found: {TOC_CORRECTED}")
        return

    with open(TOC_CORRECTED) as f:
        toc = json.load(f)

    flat = flatten_toc(toc)

    with open(TOC_FLAT, "w") as f:
        json.dump(flat, f, indent=2)

    print(f"✅ Flattened TOC saved to: {TOC_FLAT}")


if __name__ == "__main__":
    main()
