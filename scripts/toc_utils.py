import re
from typing import List, Tuple, Dict
from pathlib import Path
import json
import unicodedata


def extract_raw_toc_lines(text: str) -> List[str]:
    """Split OCR'd text into TOC lines."""
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            lines.append(clean)
    return lines

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    return text.lower().strip("_")

def generate_page_mapping(entries: List[Tuple[str, int]], logical_start: int, image_start: int) -> Dict[str, str]:
    """Map logical TOC entries to image filenames based on offset."""
    offset = image_start - logical_start
    mapping = {}
    for title, page in entries:
        image_page = page + offset
        mapping[title] = f"page_{image_page:03d}.png"
    return mapping

    from pathlib import Path
import json

def load_table_metadata(path: Path) -> list:
    """Loads TOC table metadata from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"❌ TOC metadata not found: {path}")
    with open(path) as f:
        return json.load(f)