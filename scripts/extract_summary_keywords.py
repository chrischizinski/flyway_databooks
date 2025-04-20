import json
import re
from collections import Counter
from pathlib import Path

FEEDBACK_PATH = Path("data/row_feedback.json")

def load_feedback():
    with open(FEEDBACK_PATH) as f:
        return json.load(f)["feedback"]

def extract_keywords(feedback_rows, label):
    all_words = []
    for entry in feedback_rows:
        if entry["true_type"] != label:
            continue
        text = " ".join(entry["row"]).lower()
        all_words.extend(re.findall(r"\b\w+\b", text))

    word_counts = Counter(all_words)
    # Filter out very short/common terms
    return {
        word for word, count in word_counts.items()
        if count >= 2 and len(word) >= 4
    }

def main():
    feedback = load_feedback()

    summary_terms = extract_keywords(feedback, "summary")
    footnote_terms = extract_keywords(feedback, "footnote")

    print("\n📊 Suggested Summary Keywords:")
    for word in sorted(summary_terms):
        print("  -", word)

    print("\n📎 Suggested Footnote Keywords:")
    for word in sorted(footnote_terms):
        print("  -", word)

if __name__ == "__main__":
    main()