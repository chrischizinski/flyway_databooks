from pathlib import Path

def load_config():
    base_dir = Path(__file__).resolve().parent.parent
    config = {
        "input_dir": base_dir / "data" / "input",
        "output_dir": base_dir / "data" / "output",
        "regex": {
            "year": r"\\b(19|20)\\d{2}\\b",
            "page_number": r"Page\\s\\d+",
            "section": r"Section\\s\\d+",
        },
    }
    return config
