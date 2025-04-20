import re
from typing import List, Dict

SUMMARY_KEYWORDS = {"average", "mean", "total", "summary", "median", "aggregate"}
FOOTNOTE_PATTERNS = [
    r"source", r"note", r"see appendix", r"\\*", r"data provided by",
    r"\d+\s+preliminary", r"harvest information program"
]


LABEL_PRIORITY = {
    "header": 0,
    "data": 1,
    "summary": 2,
    "footnote": 3,
    "caption": 4,
    "broken": 5,
}


def classify_row(text: str) -> str:
    row = text.lower()
    if any(re.search(pattern, row) for pattern in FOOTNOTE_PATTERNS):
        return "footnote"
    if any(word in row for word in SUMMARY_KEYWORDS):
        return "summary"
    if re.match(r"^(\s*[a-z]{2,}\s*){2,}$", row):
        return "header"
    return "data"


def clean_rows(labeled: List[Dict]) -> List[List[str]]:
    cleaned = []
    for row in labeled:
        if row["label"] in ("summary", "footnote", "caption", "broken"):
            continue
        cleaned.append(row["cells"])
    return cleaned


def is_valid_row(row: List[str]) -> bool:
    non_empty = [cell for cell in row if cell.strip()]
    return len(non_empty) >= 2
