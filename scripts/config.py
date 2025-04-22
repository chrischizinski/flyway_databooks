# config.py
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
ORIGINAL_DATA_DIR = DATA_DIR / "original"
OUTPUT_DIR = DATA_DIR

# File paths
INPUT_FILES = {
    "fish": ORIGINAL_DATA_DIR / "fish_data.csv",
    "harvest": ORIGINAL_DATA_DIR / "harvest_data.csv",
    "hunter": ORIGINAL_DATA_DIR / "hunter_data.csv",
    # Add other data files here
}

OUTPUT_FILES = {
    "fish": OUTPUT_DIR / "fish.json",
    "harvest": OUTPUT_DIR / "harvest.json",
    "hunter": OUTPUT_DIR / "hunter.json",
    # Add other output files here
}

# Column mappings and data schemas
COLUMN_MAPPINGS = {
    "fish": {
        # map column names to standardized names
        "original_col1": "standardized_col1",
        # other mappings
    },
    # mappings for other data types
}

# Processing configurations 
PROCESSING_CONFIG = {
    "fish": {
        "dtypes": {"col1": "int", "col2": "str"},
        "date_columns": ["date_col1", "date_col2"],
    },
    # configs for other data types
}