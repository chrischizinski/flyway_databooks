import pandas as pd
from typing import List


def parse_table_from_text(text_lines: List[str]) -> pd.DataFrame:
    """
    Example parser: extracts tabular data from a list of text lines.
    Replace with your own parsing logic depending on actual structure.
    """
    records = []
    for line in text_lines:
        columns = line.split()
        if len(columns) >= 3:
            records.append(columns)

    df = pd.DataFrame(records)
    return df


def clean_table(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize, clean and type-correct a DataFrame."""
    df.columns = [f"col_{i}" for i in range(df.shape[1])]
    df = df.dropna(how="all")
    return df.reset_index(drop=True)
