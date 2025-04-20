import re
from scripts.classify_row_dynamic import SUMMARY_KEYWORDS, FOOTNOTE_PATTERNS

def is_mostly_empty(row):
    return sum(1 for cell in row if cell.strip()) < len(row) * 0.25

def is_mostly_numeric(row):
    num_cells = sum(1 for cell in row if re.match(r"^[\d,\.]+$", cell.strip()))
    return num_cells >= len(row) * 0.6

def classify_row(row, row_index=0, total_rows=None):
    row_lc = [cell.lower().strip() for cell in row if cell.strip()]
    first_cell = row_lc[0] if row_lc else ""

    # Footnotes
    if is_mostly_empty(row) or any(re.search(pat, " ".join(row_lc)) for pat in FOOTNOTE_PATTERNS):
        return "footnote"

    # Summary
    if first_cell in SUMMARY_KEYWORDS or any(k in first_cell for k in SUMMARY_KEYWORDS):
        return "summary"

    if total_rows and row_index >= total_rows - 2:
        if any(k in first_cell for k in SUMMARY_KEYWORDS):
            return "summary"

    # Header
    if row_index == 0 and not is_mostly_numeric(row):
        return "header"

    # Default
    return "data"