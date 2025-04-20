#!/usr/bin/env python3
"""
Flyway Databook Pipeline Runner

This script provides a convenient way to run the complete data extraction pipeline
or specific steps from the documented process in the README.md file.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
SCRIPTS_DIR = ROOT / "scripts"

# Define all steps in the pipeline
PIPELINE_STEPS = [
    {
        "id": 1,
        "name": "extract_toc",
        "script": "extract_toc_from_pdf",
        "description": "Extract Table of Contents from PDF",
        "args": ["--start", "4", "--end", "5", "--output", "data/toc_hierarchical.json"]
    },
    {
        "id": 2,
        "name": "flatten_toc",
        "script": "flatten_toc",
        "description": "Flatten hierarchical TOC structure",
        "args": ["--input", "data/toc_hierarchical.json", "--output", "data/toc_flat.json"]
    },
    {
        "id": 3,
        "name": "generate_cleaned",
        "script": "generate_toc_cleaned",
        "description": "Generate cleaned TOC for processing",
        "args": ["--input", "data/toc_flat.json"]
    },
    {
        "id": 4,
        "name": "map_pages",
        "script": "map_toc_to_images",
        "description": "Map TOC pages to image files",
        "args": ["--first-numbered-page", "1", "--first-image-page", "7", 
                "--input", "data/toc_flat.json", "--output", "data/toc_page_mapping.json"]
    },
    {
        "id": 5,
        "name": "spell_check",
        "script": "spell_check_titles_interactive",
        "description": "Spell-check and correct TOC titles",
        "args": ["--pdf-name", "central_flyway_databook_2023", "--interactive"]
    },
    {
        "id": 6,
        "name": "verify_captions",
        "script": "toc_caption_verifier",
        "description": "Match TOC entries to page captions",
        "args": ["--input", "data/toc_flat.json", "--output", "data/toc_table_metadata.json"]
    },
    {
        "id": 7,
        "name": "extract_tables",
        "script": "extract_table_pages",
        "description": "Extract tables from pages",
        "args": ["--clean", "--metadata", "data/toc_table_metadata.json"]
    },
    {
        "id": 8,
        "name": "label_rows",
        "script": "row_feedback_logger",
        "description": "Log and label misclassified/unknown rows",
        "args": ["--tables-dir", "tables_extracted"]
    },
    {
        "id": 9,
        "name": "train_classifier",
        "script": "train_row_classifier",
        "description": "Train the ML classifier on feedback",
        "args": ["--output", "row_classifier/model"]
    }
]

def run_step(step, verbose=False):
    """Run a specific pipeline step."""
    script_path = SCRIPTS_DIR / step["script"]
    module_name = f"scripts.{step['script']}"
    
    print(f"\n{'='*80}")
    print(f"STEP {step['id']}: {step['description']}")
    print(f"{'='*80}")
    
    cmd = [sys.executable, "-m", module_name] + step["args"]
    
    if verbose:
        print(f"Running command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print(f"\n✅ Step {step['id']} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Step {step['id']} failed with error code {e.returncode}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Run the Flyway Databook extraction pipeline")
    parser.add_argument("--step", type=int, help="Run a specific step (1-9)", default=None)
    parser.add_argument("--from-step", type=int, help="Start pipeline from this step", default=1)
    parser.add_argument("--to-step", type=int, help="End pipeline at this step", default=9)
    parser.add_argument("--all", action="store_true", help="Run all steps")
    parser.add_argument("--list", action="store_true", help="List all available steps")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable Pipeline Steps:")
        print("-"*80)
        for step in PIPELINE_STEPS:
            print(f"{step['id']}. {step['description']}")
        return

    if args.step is not None:
        # Run a specific step
        step = next((s for s in PIPELINE_STEPS if s["id"] == args.step), None)
        if not step:
            print(f"Error: Step {args.step} not found")
            return
        run_step(step, args.verbose)
    elif args.all or (args.from_step or args.to_step):
        # Run a range of steps
        from_step = args.from_step
        to_step = args.to_step
        
        steps_to_run = [s for s in PIPELINE_STEPS if from_step <= s["id"] <= to_step]
        
        print(f"\nRunning pipeline steps {from_step} to {to_step}")
        for step in steps_to_run:
            success = run_step(step, args.verbose)
            if not success:
                print("\n⚠️ Pipeline stopped due to step failure")
                break
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
