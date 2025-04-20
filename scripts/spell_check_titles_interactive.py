import argparse
from pathlib import Path
from spell_check_titles import correct_titles_from_json

def main():
    parser = argparse.ArgumentParser(description="Spell check and clean TOC titles.")
    parser.add_argument("--input", type=Path, required=True, help="Input TOC cleaned JSON file")
    parser.add_argument("--dict", type=Path, required=True, help="SymSpell dictionary path (txt file)")
    parser.add_argument("--output", type=Path, required=True, help="Path to save corrected titles JSON")
    parser.add_argument("--known", type=Path, required=True, help="Path to known_titles.json file")
    parser.add_argument("--interactive", action="store_true", help="Enable interactive confirmation")

    args = parser.parse_args()

    correct_titles_from_json(
        input_path=args.input,
        dict_path=args.dict,
        output_path=args.output,
        known_path=args.known,
        interactive=args.interactive
    )

if __name__ == "__main__":
    main()

