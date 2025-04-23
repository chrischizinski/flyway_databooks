import argparse
from pathlib import Path
from table_processor import TableProcessor
from config import load_config


def main():
    parser = argparse.ArgumentParser(description="Flyway Databook Processor")
    parser.add_argument("--input", type=str, required=True, help="Directory containing PDF files")
    parser.add_argument("--output", type=str, required=True, help="Directory to save CSV outputs")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config()

    processor = TableProcessor(input_dir, output_dir, config)
    processor.run()


if __name__ == "__main__":
    main()