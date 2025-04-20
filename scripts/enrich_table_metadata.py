import re
import json
import pdfplumber
from pathlib import Path


def enrich_toc_with_clean_captions(pdf_path: Path, toc_metadata: list, save_to: Path = None):
    """
    Enriches TOC metadata with matched and cleaned unmatched table captions from corresponding PDF pages.

    Filters out:
    - Footer junk (e.g., "Central Flyway Databook", drive paths)
    - Numeric-only or mostly-numeric lines
    - Very short strings (≤ 3 words)

    Args:
        pdf_path (Path): Path to the source PDF.
        toc_metadata (list): List of TOC entries with at least title and page keys.
        save_to (Path, optional): If provided, saves the enriched metadata to this file.

    Returns:
        list: Enriched TOC metadata entries.
    """

    def extract_text_lines(page):
        text = page.extract_text()
        return [line.strip() for line in text.split("\n") if len(line.strip()) > 20] if text else []

    def expand_title_variants(toc_title):
        toc_title = toc_title.replace("&", "and")
        parts = re.split(r",|\band\b", toc_title, flags=re.IGNORECASE)
        return list({p.strip() for p in parts if p.strip()})

    def match_captions_to_terms(captions, terms):
        matched = []
        for caption in captions:
            caption_lc = caption.lower()
            for term in terms:
                if term.lower() in caption_lc:
                    matched.append(caption)
                    break
        return matched

    def is_noise_line(line):
        line_lc = line.lower()
        return (
            any(p in line_lc for p in [
                "central flyway databook", "project", "s:\\", "c:\\", "page", "preliminary",
                "harvest information program", "prepared by", "updated", "download", "https://", ".gov", ".pdf"
            ]) or
            re.match(r"^[0-9\s\.,%-]+$", line) or
            len(line.split()) < 4
        )

    enriched_all = []

    with pdfplumber.open(pdf_path) as pdf:
        for entry in toc_metadata:
            title = entry["title"]
            page = entry["page"]
            pdf_index = entry.get("pdf_index", page - 1)

            if pdf_index >= len(pdf.pages):
                continue

            page_obj = pdf.pages[pdf_index]
            lines = extract_text_lines(page_obj)
            terms = expand_title_variants(title)
            matched = match_captions_to_terms(lines, terms)
            unmatched = [l for l in lines if l not in matched]
            unmatched_cleaned = [l for l in unmatched if not is_noise_line(l)]

            enriched_entry = {
                "title": title,
                "section": entry.get("section"),
                "page": page,
                "pdf_index": pdf_index,
                "slug": entry.get("slug"),
                "matched_tables": [{"caption": cap} for cap in matched],
                "unmatched_captions": unmatched_cleaned
            }
            enriched_all.append(enriched_entry)

    if save_to:
        save_to.parent.mkdir(parents=True, exist_ok=True)
        with open(save_to, "w") as f:
            json.dump(enriched_all, f, indent=2)
        print(f"✅ Cleaned TOC metadata saved to {save_to}")

    return enriched_all