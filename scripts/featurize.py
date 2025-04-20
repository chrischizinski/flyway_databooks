import re
import numpy as np
from scripts.classify_row_dynamic import SUMMARY_KEYWORDS, FOOTNOTE_PATTERNS


def is_year(text):
    return bool(re.match(r"^\d{4}(-\d{2})?$", text.strip()))


def is_numeric(text):
    return bool(re.match(r"^[\d,.]+$", text.strip()))


def has_summary_keyword(text):
    return any(k in text.lower() for k in SUMMARY_KEYWORDS)


def has_footnote(text):
    return any(re.search(pat, text.lower()) for pat in FOOTNOTE_PATTERNS)


def extract_features(row):
    tokens = [cell.strip() for cell in row if cell.strip()]
    num_tokens = len(tokens)
    numeric_tokens = sum(is_numeric(tok) for tok in tokens)
    pct_numeric = numeric_tokens / num_tokens if num_tokens > 0 else 0
    upper_tokens = sum(tok.isupper() for tok in tokens)

    row_text = " ".join(tokens)

    features = {
        "starts_with_year": int(is_year(tokens[0]) if tokens else False),
        "has_summary_keyword": int(has_summary_keyword(row_text)),
        "has_footnote": int(has_footnote(row_text)),
        "num_tokens": num_tokens,
        "num_numeric": numeric_tokens,
        "pct_numeric": pct_numeric,
        "upper_ratio": upper_tokens / num_tokens if num_tokens > 0 else 0
    }

    return features


def extract_feature_matrix(rows):
    return [extract_features(row) for row in rows]


def feature_names():
    return [
        "starts_with_year",
        "has_summary_keyword",
        "has_footnote",
        "num_tokens",
        "num_numeric",
        "pct_numeric",
        "upper_ratio"
    ]
