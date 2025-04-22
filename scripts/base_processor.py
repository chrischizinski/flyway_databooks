# base_processor.py
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Union
from abc import ABC, abstractmethod

from utils import read_csv, rename_columns, save_to_json, validate_data
import config

class DataProcessor(ABC):
    """Base class for all data processors."""
    
    def __init__(
        self,
        data_type: str,
        input_file: Optional[Union[str, Path]] = None,
        output_file: Optional[Union[str, Path]] = None
    ):
        self.data_type = data_type
        self.input_file = input_file or config.INPUT_FILES.get(data_type)
        self.output_file = output_file or config.OUTPUT_FILES.get(data_type)
        self.column_mapping = config.COLUMN_MAPPINGS.get(data_type, {})
        self.processing_config = config.PROCESSING_CONFIG.get(data_type, {})
        self.df = None
    
    def load_data(self, **kwargs):
        """Load data from input file."""
        dtypes = self.processing_config.get("dtypes")
        date_columns = self.processing_config.get("date_columns")
        
        self.df = read_csv(
            self.input_file,
            dtypes=dtypes,
            date_columns=date_columns,
            **kwargs
        )
        
        # Apply column renaming if mapping exists
        if self.column_mapping:
            self.df = rename_columns(self.df, self.column_mapping)
        
        return self
    
    @abstractmethod
    def process(self):
        """Process the data - must be implemented by subclasses."""
        pass
    
    def save(self, orient="records"):
        """Save processed data to output file."""
        if self.df is None:
            raise ValueError("No data to save. Make sure to load and process data first.")
        
        save_to_json(self.df, self.output_file, orient=orient)
        return self
    
    def run(self, **kwargs):
        """Run the full processing pipeline."""
        return self.load_data(**kwargs).process().save()