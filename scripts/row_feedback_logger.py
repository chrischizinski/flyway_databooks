import json
import glob
from pathlib import Path
from tqdm import tqdm
import re

# Paths
ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = ROOT / "tables_extracted"
FEEDBACK_PATH = ROOT / "data" / "row_feedback.json"

LABEL_MAP = {
    "h": "header",
    "d": "data",
    "s": "summary",
    "f": "footnote",
    "x": "broken",
    "c": "caption"
}

# Load previous feedback if it exists
if FEEDBACK_PATH.exists():
    with open(FEEDBACK_PATH) as f:
        feedback = json.load(f)
else:
    feedback = []

seen_rows = {json.dumps(entry["row"]) for entry in feedback}

print("🔍 Starting interactive labeling loop")
print("Labels: [h]eader, [d]ata, [s]ummary, [f]ootnote, [c]aption, [x]broken, [enter=skip], q=quit\n")

# Footnote extraction from bottom of table page
footnote_lookup = {}
def extract_footnotes(footer_text):
    lines = footer_text.split("\n")
    for line in lines:
        match = re.match(r"^(\d+)\s+(.*)$", line.strip())
        if match:
            footnote_lookup[match.group(1)] = match.group(2).strip()

# Cleaner that handles superscripts and commas

def clean_cell(cell: str):
    cell = cell.strip()
    cell = re.sub(r'(?<=\d),(?=\d)', '', cell)  # Remove commas in numbers

    # Detect and isolate superscripts like "2003 1"
    superscript_note = None
    if re.match(r'^\d+ \d+$', cell):
        base, superscript_note = cell.split()
    elif re.match(r'^\w+ \d$', cell):
        base, superscript_note = cell.rsplit(' ', 1)
    else:
        base = cell

    # Enrich with note text if available
    if superscript_note and superscript_note in footnote_lookup:
        return f"{base} ({footnote_lookup[superscript_note]})"

    return base

# Heuristic to detect suspicious rows
def is_suspicious_row(row):
    cleaned = [c for c in row if c.strip() and c.strip().lower() != 'total']
    if len(cleaned) <= 2:
        return True
    if all(re.fullmatch(r'\d{4}', c) for c in cleaned):  # only years
        return True
    numeric = sum(1 for c in cleaned if re.fullmatch(r'[-+]?[0-9]*\.?[0-9]+', c))
    empty = sum(1 for c in cleaned if not c.strip())
    zeros = sum(1 for c in cleaned if c.strip() == '0')

    if len(cleaned) > 0:
        pct_numeric = numeric / len(cleaned)
        pct_empty = empty / len(row)
        pct_zeros = zeros / len(cleaned)
        if pct_empty > 0.5 or pct_zeros > 0.9:
            return True
    return False

# Gather all new rows and captions
unlabeled = []

for file_path in sorted(TABLES_DIR.glob("*.json")):
    with open(file_path) as f:
        table = json.load(f)

    title = table.get("title")
    page = table.get("actual_page")
    caption = table.get("caption")
    footnotes = table.get("footnotes", "")

    # Build footnote mapping
    extract_footnotes(footnotes)

    if caption:
        row_key = json.dumps([caption])
        if row_key not in seen_rows:
            unlabeled.append((file_path.name, page, title, [caption]))

    if "headers" in table and isinstance(table["headers"], list):
        # Merge all headers into a single row
        merged_headers = []
        for row in table["headers"]:
            if isinstance(row, list):
                merged_headers.extend(row)
        if merged_headers:
            row_key = json.dumps(merged_headers)
            if row_key not in seen_rows:
                print(f"➡️ Adding merged headers from {file_path.name}: {merged_headers}")
                unlabeled.append((file_path.name, page, title, merged_headers))

    if "rows" in table and isinstance(table["rows"], list):
        for row in table["rows"]:
            row_key = json.dumps(row)
            if row_key not in seen_rows:
                unlabeled.append((file_path.name, page, title, row))

# Start interactive labeling with progress
for i, (filename, page, title, row) in enumerate(tqdm(unlabeled, desc="Labeling progress", dynamic_ncols=True, mininterval=0.1)):
    row = [row] if isinstance(row, str) else row  # Ensure row is a list
    cleaned_row = [clean_cell(c) for c in row]

    print(f"\n📄 File: {filename} (Page {page})")
    print(f"📝 Title: {title}")
    print(f"Row: {' | '.join(cleaned_row)}")

    if is_suspicious_row(cleaned_row):
        print("⚠️ Suspicious row: may be missing data, empty, zero-filled or only year-like values")

    label = input("Label this row [h/d/s/f/c/x, enter=skip, q=quit]: ").strip().lower()

    if label == "q":
        print("👋 Exiting...")
        break
    elif label in LABEL_MAP:
        feedback.append({"row": cleaned_row, "true_type": LABEL_MAP[label]})
        seen_rows.add(json.dumps(cleaned_row))
        print(f"✅ Logged as {LABEL_MAP[label]}")
    else:
        print("⏭️ Skipped")

# Save updated feedback
with open(FEEDBACK_PATH, "w") as f:
    json.dump(feedback, f, indent=2)

print(f"\n💾 Feedback saved to: {FEEDBACK_PATH}")
