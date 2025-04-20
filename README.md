# 📘 Flyway Databook Pipeline

This project extracts and processes tabular data from scanned PDF documents (e.g., Central Flyway Databook) using a mix of layout parsing, text extraction, ML-based row classification, and fuzzy TOC alignment. The pipeline transforms complex PDF tables into structured data stored in both SQLite database tables and JSON formats for further analysis.

---

## 🔧 Setup

```bash
pip install -r requirements.txt
```

## 🚀 Quick Start

You can run the entire pipeline or specific steps using the main.py runner:

```bash
# List all available steps
./main.py --list

# Run the entire pipeline
./main.py --all

# Run a specific step (e.g., step 5 - spell check)
./main.py --step 5

# Run a range of steps (e.g., steps 3-6)
./main.py --from-step 3 --to-step 6

# Add verbose output
./main.py --all --verbose
```

---

## 🗂️ Step-by-Step Process

### 1. Convert PDF to TOC JSON
Extract the Table of Contents directly from a PDF:
```bash
python -m scripts.extract_toc_from_pdf \
  --start 4 \
  --end 5 \
  --output data/toc_hierarchical.json
```

### 2. Flatten the Hierarchical TOC (if needed)
```bash
python -m scripts.flatten_toc \
  --input data/toc_hierarchical.json \
  --output data/toc_flat.json
```

### 3. Generate Cleaned TOC for Interactive Tools
Creates both `toc_cleaned.json` and `toc_table_metadata.json` files for subsequent steps:
```bash
python -m scripts.generate_toc_cleaned \
  --input data/toc_flat.json
```

### 4. Map TOC pages to image files
```bash
python -m scripts.map_toc_to_images \
  --first-numbered-page 1 \
  --first-image-page 7 \
  --input data/toc_flat.json \
  --output data/toc_page_mapping.json
```

### 5. Spell-check and correct TOC titles
```bash
python -m scripts.spell_check_titles_interactive \
  --pdf-name central_flyway_databook_2023 \
  --interactive
```

### 6. Match TOC entries to page captions
Verifies TOC entries against extracted captions from PDF pages:
```bash
python -m scripts.toc_caption_verifier \
  --input data/toc_flat.json \
  --output data/toc_table_metadata.json
```

### 7. Extract tables from each page
```bash
python -m scripts.extract_table_pages \
  --clean \
  --metadata data/toc_table_metadata.json
```

### 8. Log and label misclassified or unknown rows interactively
```bash
python -m scripts.row_feedback_logger \
  --tables-dir tables_extracted
```

### 9. Train the ML classifier on feedback
```bash
python -m scripts.train_row_classifier \
  --output row_classifier/model
```

---

## 📦 Outputs
- `tables_extracted/` → Clean JSON files per table
- `data/toc_table_metadata.json` → Verified TOC + captions
- `row_classifier/model/` → Saved XGBoost + scaler
- `database/flyway_data.db` → SQLite database with extracted table data

## 🗃️ Database Structure
The SQLite database contains:
- Individual tables named with format `ce_2023_XXX` (one per extracted table)
- A `table_index` table that catalogs all extracted tables

---

## ✅ Tips
- Use `--clean` to refresh extracted tables
- Always use `toc_flat.json` instead of `toc_hierarchical.json` in mapping scripts
- Use `toc_cleaned.json` for spell checking & legacy utilities

## 🔍 Troubleshooting

### Common Issues
- **Missing TOC files**: Ensure each step generates its expected output files before proceeding
- **OCR Quality Issues**: If table extraction is poor, try adjusting the page parameters in step 4
- **Row Classification Errors**: Add more training examples in step 8 if specific row types are misclassified

### Step Dependencies
- Step 3 depends on step 2's output (`toc_flat.json`)
- Step 5 depends on step 3's output (`toc_cleaned.json`)
- Step 6 depends on step 4's output (page mappings)
- Step 7 depends on step 6's output (`toc_table_metadata.json`)

### Error Recovery
- If a step fails, check the specific output files that should have been generated
- You can re-run individual steps without restarting the entire pipeline
- For classification issues, add more training examples rather than modifying the model directly

---

## 📁 Key Folders
- `data/` → Inputs, TOC files, and extracted content
  - `data/images/` → Extracted page images from PDF
  - `data/tables_ocr/` → Raw CSV files from OCR process
  - `data/symspell/` → Dictionary files for spell checking
  - `data/toc_known_titles/` → Saved corrected titles by PDF
- `tables_extracted/` → Output table data in JSON format
- `database/` → SQLite database with extracted tables
- `scripts/` → Processing pipeline scripts
- `row_classifier/` → Machine learning model for row classification
