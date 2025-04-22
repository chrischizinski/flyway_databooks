# utils.py
import pandas as pd
import json
import logging
from typing import Dict, List, Union, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_csv(
    filepath: Union[str, Path], 
    dtypes: Optional[Dict] = None,
    date_columns: Optional[List[str]] = None,
    **kwargs
) -> pd.DataFrame:
    """Read a CSV file with standard error handling and data type conversion."""
    try:
        df = pd.read_csv(filepath, **kwargs)
        
        # Apply data types if provided
        if dtypes:
            for col, dtype in dtypes.items():
                if col in df.columns:
                    try:
                        df[col] = df[col].astype(dtype)
                    except Exception as e:
                        logger.warning(f"Could not convert column {col} to {dtype}: {e}")
        
        # Convert date columns if provided
        if date_columns:
            for col in date_columns:
                if col in df.columns:
                    try:
                        df[col] = pd.to_datetime(df[col])
                    except Exception as e:
                        logger.warning(f"Could not convert column {col} to datetime: {e}")
        
        logger.info(f"Successfully read data from {filepath} with {len(df)} rows")
        return df
    
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        raise

def rename_columns(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Rename DataFrame columns based on a mapping dictionary."""
    # Only rename columns that exist in the DataFrame
    valid_mapping = {k: v for k, v in mapping.items() if k in df.columns}
    if valid_mapping:
        df = df.rename(columns=valid_mapping)
    return df

def save_to_json(
    data: Union[Dict, List, pd.DataFrame],
    output_path: Union[str, Path],
    orient: str = "records",
    date_format: str = "iso"
) -> None:
    """Save data to a JSON file with standard error handling."""
    try:
        # Create directory if it doesn't exist
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert DataFrame to dict/list if needed
        if isinstance(data, pd.DataFrame):
            data = data.to_dict(orient=orient)
        
        # Save to JSON
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Successfully saved data to {output_path}")
    
    except Exception as e:
        logger.error(f"Error saving to {output_path}: {e}")
        raise

def validate_data(df: pd.DataFrame, required_columns: List[str]) -> bool:
    """Validate that DataFrame contains required columns."""
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.warning(f"Missing required columns: {missing_columns}")
        return False
    return True