import json
import re
from collections import Counter
from pathlib import Path

FEEDBACK_PATH = Path("data/row_feedback.json")
OUTPUT_PATH = Path("scripts/classify_row_dynamic.py")

def load_feedback():
    with open(FEEDBACK_PATH) as f:
        return json.load(f)["feedback"]

def extract_keywords(feedback, label):
    words = []
    for entry in feedback:
        if entry["true_type"] != label:
            continue
        text = " ".join(entry["row"]).lower()
        words += re.findall(r"\b\w+\b", text)
    freq = Counter(words)
    return sorted({w for w, c in freq.items() if c >= 2 and len(w) >= 4})

def build_classifier_module(summary_keywords, footnote_terms):
    return f'''"""
Auto-generated keyword constants from feedback.

To regenerate: python scripts/update_keyword_constants.py
"""

SUMMARY_KEYWORDS = {summary_keywords}
FOOTNOTE_PATTERNS = {footnote_terms}
'''

def main():
    feedback = load_feedback()
    summary = extract_keywords(feedback, "summary")
    footnotes = extract_keywords(feedback, "footnote")

    # Build regex patterns for footnotes
    footnote_regexes = [rf"{term}" for term in footnotes]

    module_text = build_classifier_module(summary, footnote_regexes)

    OUTPUT_PATH.write_text(module_text)
    print(f"✅ Constants updated in: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()