import shutil
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = ROOT / "scripts"
BACKUP_JSON = DATA_DIR / "_backup_old_jsons"
BACKUP_PY = SCRIPTS_DIR / "_archive_unused"
BACKUP_JSON.mkdir(exist_ok=True)
BACKUP_PY.mkdir(exist_ok=True)

# JSON files to move
FILES_TO_BACKUP = [
    DATA_DIR / "toc_cleaned.json",
    DATA_DIR / "toc_corrected.json"
]

# Python scripts to archive (manually reviewed list)
UNUSED_PY_FILES = [
    "generate_toc_cleaned.py",  # replaced by extract_toc_from_pdf
    "spell_check_titles_interactive.py",  # superseded by fuzzy matcher
    "parse_toc_and_extract.py",  # absorbed by modern extractor
    "ocr.py",  # old OCR wrapper
    "ocr_tables.py",  # replaced by layout-aware extractor
    "test.py"  # dev scratchpad
]

# Move JSON files
for path in FILES_TO_BACKUP:
    if path.exists():
        dest = BACKUP_JSON / path.name
        shutil.move(str(path), str(dest))
        print(f"📦 Moved JSON to backup: {path.name}")
    else:
        print(f"❌ Missing JSON: {path.name}")

# Move deprecated Python scripts
for name in UNUSED_PY_FILES:
    src = SCRIPTS_DIR / name
    if src.exists():
        dest = BACKUP_PY / name
        shutil.move(str(src), str(dest))
        print(f"📦 Archived script: {name}")
    else:
        print(f"❌ Missing script: {name}")

print("\n✅ Cleanup complete.")