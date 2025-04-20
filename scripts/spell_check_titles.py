
import json
import re
from pathlib import Path
from symspellpy import SymSpell, Verbosity
from titlecase import titlecase

WHITELIST = {
    "wood duck": "Wood Duck", "cf": "CF", "u.s.": "U.S.", "hip": "HIP", "scaup": "Scaup",
    "ross's": "Ross’s", "ahm": "AHM", "game": "Game", "sandhill": "Sandhill", "mallard": "Mallard",
    "gadwall": "Gadwall", "wigeon": "Wigeon", "goose": "Goose", "duck": "Duck", "minnesota": "Minnesota",
    "permit": "Permit", "permits": "Permits", "harvest": "Harvest", "swans": "Swans", "swan": "Swan",
    "canada": "Canada", "usfws": "USFWS", "wbphs": "WBPHS", "hr": "HR", "nawmp": "NAWMP",
    "fws": "FWS", "dnr": "DNR", "per": "Per", "x": "X", "cfan": "CFAN"
}

def load_symspell(dict_path: Path):
    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    if not sym_spell.load_dictionary(dict_path, term_index=0, count_index=1):
        raise RuntimeError("Failed to load SymSpell dictionary")
    return sym_spell

def normalize_title(text: str) -> str:
    """
    Normalize a TOC title:
    - Strip trailing dots (leader lines)
    - Preserve commas, slashes, and conjunctions
    - Standardize dashes, apostrophes, and spacing
    """
    # Remove trailing dot leaders
    text = re.sub(r"[.]{3,}$", "", text)

    # Normalize various punctuation
    text = text.replace("‐", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')

    # Normalize spacing around punctuation
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*'\s*", "'", text)
    text = re.sub(r"\s*-\s*", "-", text)

    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip(" .")

def spell_correct_title(sym_spell: SymSpell, title: str, interactive=False) -> str:
    normalized = normalize_title(title.lower())
    tokens = normalized.split()
    corrected = []
    for token in tokens:
        if token in WHITELIST:
            corrected.append(WHITELIST[token])
        else:
            suggestions = sym_spell.lookup(token, Verbosity.TOP, max_edit_distance=2)
            corrected_token = suggestions[0].term if suggestions else token
            corrected.append(corrected_token)
    corrected_title = titlecase(" ".join(corrected))

    if interactive:
        print(f"
Original : {title}")
        print(f"Suggested: {corrected_title}")
        response = input("Accept suggestion? [Y/n/custom]: ").strip().lower()
        if response == "n":
            return title
        elif response and response != "y":
            return response
    return corrected_title




def load_known_titles(path: Path) -> set:
    if path.exists():
        with open(path) as f:
            return set(json.load(f))
    return set()

def save_known_titles(path: Path, known_titles: set):
    with open(path, "w") as f:
        json.dump(sorted(known_titles), f, indent=2)

def correct_titles_from_json(input_path: Path, dict_path: Path, output_path: Path, known_path: Path, interactive=False):
    sym_spell = load_symspell(dict_path)
    known_titles = load_known_titles(known_path)

    with open(input_path) as f:
        toc_dict = json.load(f)

    corrected = {}
    for title in toc_dict:
        normalized = normalize_title(title)
        if normalized in known_titles:
            corrected[title] = title
            print(f"✅ Skipped known title: {title}")
            continue

        new_title = spell_correct_title(sym_spell, title, interactive=interactive)
        print(f"
✔️  Original : {title}
🆕 Corrected: {new_title}")
        corrected[title] = new_title
        known_titles.add(normalized)

    with open(output_path, "w") as f:
        json.dump(corrected, f, indent=2)
    save_known_titles(known_path, known_titles)
    print(f"✅ Corrected TOC titles saved to {output_path}")
    print(f"📚 Known titles saved to {known_path}")
    return corrected


    corrected = {}
    for title in toc_dict:
        new_title = spell_correct_title(sym_spell, title, interactive=interactive)
        print(f"
✔️  Original : {title}
🆕 Corrected: {new_title}")
        corrected[title] = new_title

    with open(output_path, "w") as f:
        json.dump(corrected, f, indent=2)
    print(f"✅ Corrected TOC titles saved to {output_path}")
    return corrected


    corrected = {}
    for title in toc_dict:
        corrected[title] = spell_correct_title(sym_spell, title)

    with open(output_path, "w") as f:
        json.dump(corrected, f, indent=2)
    print(f"✅ Corrected TOC titles saved to {output_path}")
    return corrected