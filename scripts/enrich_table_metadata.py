import re
import json
import pdfplumber
from pathlib import Path

def enrich_toc_with_clean_captions(pdf_path: Path, toc_metadata: list, corrected_titles: dict = None, save_to: Path = None):
    def extract_text_lines(page):
        text = page.extract_text()
        return [line.strip() for line in text.split("\n") if len(line.strip()) > 20] if text else []

    def expand_title_variants(toc_title):
        toc_title = toc_title.replace("&", "and")
        parts = re.split(r",|\band\b", toc_title, flags=re.IGNORECASE)
        return list({p.strip() for p in parts if p.strip()})

    def estimate_table_count(title: str) -> int:
        num_commas = title.count(",")
        num_ands = len(re.findall(r"\band\b", title, flags=re.IGNORECASE))
        return max(1, num_commas + num_ands + 1)

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
            title = entry.get("toc_title") or entry.get("title")
            corrected_title = corrected_titles.get(title, title) if corrected_titles else title
            pdf_index = entry.get("pdf_index")
            page = entry.get("page", pdf_index + 1 if pdf_index is not None else None)

            if pdf_index is None or pdf_index >= len(pdf.pages):
                continue

            page_obj = pdf.pages[pdf_index]
            lines = extract_text_lines(page_obj)
            terms = expand_title_variants(corrected_title)
            matched = match_captions_to_terms(lines, terms)
            unmatched = [l for l in lines if l not in matched]
            unmatched_cleaned = [l for l in unmatched if not is_noise_line(l)]

            expected_count = estimate_table_count(corrected_title)
            actual_count = len(matched)
            if actual_count == expected_count:
                status = "✅ match"
            elif actual_count < expected_count:
                status = "⚠️ missing"
            else:
                status = "❗ extra"

            enriched_entry = {
                "toc_title": title,
                "corrected_title": corrected_title,
                "section": entry.get("section"),
                "page": page,
                "pdf_index": pdf_index,
                "slug": entry.get("slug"),
                "expected_table_count": expected_count,
                "actual_table_count": actual_count,
                "table_match_status": status,
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
