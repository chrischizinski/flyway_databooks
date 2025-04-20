import argparse
import json
import re
from collections import Counter
from pathlib import Path

# Paths
FEEDBACK_PATH = Path("data/row_feedback.json")
DYNAMIC_OUTPUT = Path("scripts/classify_row_dynamic.py")

def load_feedback():
    if FEEDBACK_PATH.exists():
        with open(FEEDBACK_PATH) as f:
            return json.load(f)["feedback"]
    return []

def save_feedback(data):
    with open(FEEDBACK_PATH, "w") as f:
        json.dump({"feedback": data}, f, indent=2)

def log_feedback(row, true_type, notes):
    data = load_feedback()
    entry = {"row": row, "true_type": true_type, "notes": notes}
    data.append(entry)
    save_feedback(data)
    print(f"✅ Logged row as '{true_type}': {row}")

def extract_keywords(feedback, label):
    words = []
    for entry in feedback:
        if entry["true_type"] == label:
            text = " ".join(entry["row"]).lower()
            words.extend(re.findall(r"\b\w+\b", text))
    freq = Counter(words)
    return sorted({w for w, c in freq.items() if c >= 2 and len(w) >= 4})

def update_constants():
    feedback = load_feedback()
    summary = extract_keywords(feedback, "summary")
    footnotes = extract_keywords(feedback, "footnote")

    footnote_patterns = [f"{term}" for term in footnotes]

    content = f'''"""
Auto-generated keyword constants from feedback.

To regenerate: python scripts/row_feedback_manager.py --update
"""

SUMMARY_KEYWORDS = {summary}

FOOTNOTE_PATTERNS = {footnote_patterns}
'''
    DYNAMIC_OUTPUT.write_text(content)
    print(f"🧠 Constants updated: {DYNAMIC_OUTPUT}")

def main():
    parser = argparse.ArgumentParser(description="Manage row feedback and keyword constants")
    subparsers = parser.add_subparsers(dest="command")

    # log command
    log_parser = subparsers.add_parser("log", help="Log a row misclassification")
    log_parser.add_argument("--type", required=True, help="Correct type (summary, footnote)")
    log_parser.add_argument("--row", nargs="+", required=True, help="Misclassified row content")
    log_parser.add_argument("--notes", default="", help="Optional notes")

    # update command
    subparsers.add_parser("update", help="Update keyword constants from feedback")

    args = parser.parse_args()

    if args.command == "log":
        log_feedback(args.row, args.type, args.notes)
    elif args.command == "update":
        update_constants()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()