from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseProcessor(ABC):
    def __init__(self, input_path: Path, output_path: Path, config: dict):
        self.input_path = input_path
        self.output_path = output_path
        self.config = config

    @abstractmethod
    def load(self) -> Any:
        pass

    @abstractmethod
    def process(self) -> Any:
        pass

    @abstractmethod
    def export(self) -> None:
        pass

    def run(self):
        data = self.load()
        result = self.process(data)
        self.export(result)
