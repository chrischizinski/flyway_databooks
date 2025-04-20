import argparse
import json
from pathlib import Path

def map_toc_to_images(toc, first_numbered, first_image, image_dir):
    mapping = {}
    for entry in toc:
        title = entry["title"]
        toc_page = entry["page"]
        actual_page = first_image + (toc_page - first_numbered)
        image_file = image_dir / f"page_{actual_page:03}.png"
        mapping[title] = {
            "toc_page": toc_page,
            "image_file": str(image_file)
        }
    return mapping

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-numbered-page", type=int, required=True, help="First numbered page in the TOC")
    parser.add_argument("--first-image-page", type=int, required=True, help="First image page in the image dir")
    args = parser.parse_args()

    ROOT = Path(__file__).resolve().parents[1]
    TOC_PATH = ROOT / "data" / "toc_flat.json"
    IMAGE_DIR = ROOT / "data" / "images"
    OUTPUT_PATH = ROOT / "data" / "toc_page_mapping.json"

    if not TOC_PATH.exists():
        print(f"❌ TOC not found: {TOC_PATH}")
        return

    with open(TOC_PATH) as f:
        toc = json.load(f)

    mapping = map_toc_to_images(toc, args.first_numbered_page, args.first_image_page, IMAGE_DIR)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"✅ TOC → image mapping saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()