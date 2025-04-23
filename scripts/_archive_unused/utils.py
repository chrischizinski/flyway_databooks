from pathlib import Path
import pandas as pd

def ensure_directory(path: Path):
    """Ensure the directory exists."""
    path.mkdir(parents=True, exist_ok=True)

def clean_filename(name: str) -> str:
    """Sanitize filename by removing or replacing unsafe characters."""
    return "_".join(name.strip().lower().split())

def save_dataframe(df: pd.DataFrame, path: Path):
    """Save a DataFrame to CSV."""
    df.to_csv(path, index=False)

def list_pdfs(directory: Path):
    """Return list of PDF file paths in a directory."""
    return list(directory.glob("*.pdf"))
