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
    "fws": "FWS", "dnr": "DNR", "per": "Per", "x": "X", "cfan": "CFAN",
    "n.": "N.", "a.": "A.", "s.": "S.", "e.": "E.", "w.": "W."
}

def load_symspell(dict_path: Path):
    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    if not sym_spell.load_dictionary(dict_path, term_index=0, count_index=1):
        raise RuntimeError("Failed to load SymSpell dictionary")
    return sym_spell

def normalize_title(text: str) -> str:
    text = re.sub(r"\.{3,}\s*$", "", text)
    text = text.replace("‐", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*'\s*", "'", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" .")
def spell_correct_title(sym_spell: SymSpell, title: str, interactive=False, quit_on_reject=False) -> str:
    normalized = normalize_title(title.lower())
    tokens = re.findall(r"\b\w+\.\b|\b\w+\b|[^\w\s]", normalized)
    corrected = []
    for token in tokens:
        if token.isalpha() or ('.' in token and token in WHITELIST):
            if token in WHITELIST:
                corrected.append(WHITELIST[token])
            else:
                suggestions = sym_spell.lookup(token, Verbosity.TOP, max_edit_distance=2)
                corrected_token = suggestions[0].term if suggestions else token
                corrected.append(corrected_token)
        else:
            corrected.append(token)

    reconstructed = corrected[0]
    for i in range(1, len(corrected)):
        prev, curr = corrected[i - 1], corrected[i]
        if curr in {'/', '-'} or prev in {'/', '-'}:
            reconstructed += curr
        elif curr in {',', ';', ':'}:
            reconstructed += curr
        elif prev in {',', ';', ':'}:
            reconstructed += ' ' + curr
        elif curr.isalnum() and prev.isalnum():
            reconstructed += ' ' + curr
        else:
            reconstructed += ' ' + curr
    corrected_title = titlecase(reconstructed)

    if interactive:
        print(f"\n✔️  Original : {title}\n🆕 Corrected: {corrected_title}")
        response = input("Accept suggestion? [Return = accept / n / custom / q]: ").strip().lower()
        if response == 'q':
            print("🛑 User selected 'q' — exiting now.")
            exit(1)
        elif response == 'n':
            return title
        elif response == 'custom':
            custom_input = input('Enter your custom title: ').strip()
            return custom_input if custom_input else title
        elif response:
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

def correct_titles_from_json(input_path: Path, dict_path: Path, output_path: Path, known_path: Path, interactive=False, quit_on_reject=False):
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

        new_title = spell_correct_title(sym_spell, title, interactive=interactive, quit_on_reject=quit_on_reject)
        print(f"\n✔️  Original : {title}\n🆕 Corrected: {new_title}")
        corrected[title] = new_title
        known_titles.add(normalized)

    with open(output_path, "w") as f:
        json.dump(corrected, f, indent=2)
    save_known_titles(known_path, known_titles)

    print(f"✅ Corrected TOC titles saved to {output_path}")
    print(f"📚 Known titles saved to {known_path}")
    return corrected