import json
import re
from pathlib import Path
from symspellpy import SymSpell, Verbosity
from titlecase import titlecase
import argparse

# --- Config ---
ROOT = Path(__file__).resolve().parents[1]
TOC_INPUT = ROOT / "data" / "toc_cleaned.json"
TOC_OUTPUT = ROOT / "data" / "toc_corrected.json"
GLOBAL_KNOWN_TITLES = ROOT / "data" / "toc_known_titles.json"
DICT_PATH = ROOT / "data" / "symspell" / "frequency_dictionary_en_82_765.txt"

parser = argparse.ArgumentParser()
parser.add_argument("--pdf-name", type=str, default="central_flyway_databook_2023")
parser.add_argument("--interactive", action="store_true", help="Prompt interactively for corrections")
parser.add_argument("--auto", action="store_true", help="Disable interactive prompts, apply best suggestions")
args = parser.parse_args()

LOCAL_KNOWN_TITLES = ROOT / "data" / "toc_known_titles" / f"{args.pdf_name}.json"

WHITELIST = {
    "wood duck": "Wood Duck",
    "cf": "CF",
    "u.s.": "U.S.",
    "hip": "HIP",
    "scaup": "Scaup",
    "ross's": "Ross’s",
    "ahm": "AHM",
    "game": "Game",
    "sandhill": "Sandhill",
    "mallard": "Mallard",
    "gadwall": "Gadwall",
    "wigeon": "Wigeon",
    "goose": "Goose",
    "duck": "Duck",
    "minnesota": "Minnesota",
    "permit": "Permit",
    "permits": "Permits",
    "harvest": "Harvest",
    "swans": "Swans",
    "swan": "Swan",
    "canada": "Canada",
    "usfws": "USFWS",
    "wbphs": "WBPHS",
    "hr": "HR",
    "nawmp": "NAWMP",
    "fws": "FWS",
    "dnr": "DNR",
    "per": "Per",
    "x": "X",
    "cfan": "CFAN"
}

sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not sym_spell.load_dictionary(DICT_PATH, term_index=0, count_index=1):
    raise RuntimeError("Failed to load SymSpell dictionary")

def normalize_dots_and_spacing(text):
    """
    Normalize spacing while preserving punctuation structure.
    Only strip trailing dot leaders, standardize dash types,
    and ensure consistent spacing around punctuation.
    """
    # Store original spacing pattern to preserve structure
    spacing_pattern = [c.isspace() for c in text]
    
    # Remove trailing dots only
    text = re.sub(r"[.]+$", "", text)
    
    # Standardize dash types
    text = text.replace("‐", "-").replace("–", "-")
    
    # Normalize spacing around punctuation
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*'\s*", "'", text)
    text = re.sub(r"\s*-\s*", "-", text)
    
    # Collapse multiple spaces but preserve overall structure
    text = re.sub(r"\s{2,}", " ", text).strip(" .")
    
    return text

def tokenize_with_punctuation(text):
    """
    Tokenizes words while carefully preserving all punctuation as separate tokens.
    This ensures we don't lose any structural elements during correction.
    """
    # More comprehensive regex to catch all necessary punctuation
    # Include apostrophes and periods within words, but separate other punctuation
    return re.findall(r"[A-Za-z0-9'.]+|[,/\-:;()\[\]{}]", text)

def correct_tokens(tokens, whitelist, sym_spell, interactive=False):
    """
    Apply corrections to tokens while preserving structure.
    Handles multi-word whitelist terms and applies SymSpell
    suggestions only for non-whitelisted words.
    """
    corrected = []
    i = 0
    while i < len(tokens):
        matched = False
        # Try to match multi-word phrases first (longest to shortest)
        for n in range(5, 0, -1):
            if i + n <= len(tokens):
                # Get potential phrase (handling punctuation)
                phrase_tokens = tokens[i:i+n]
                phrase = " ".join([t for t in phrase_tokens if re.match(r"^[\w']+$", t)])
                if phrase.lower() in whitelist:
                    corrected.append(whitelist[phrase.lower()])
                    i += n
                    matched = True
                    break
        
        if matched:
            continue

        token = tokens[i]
        if re.match(r"^[\w']+$", token):  # Only spellcheck plain words
            lower_token = token.lower()
            # Check whitelist before applying SymSpell
            if lower_token in whitelist:
                corrected.append(whitelist[lower_token])
            else:
                # Only get suggestions for words not in whitelist
                suggestions = sym_spell.lookup(lower_token, Verbosity.CLOSEST, max_edit_distance=2)
                best = suggestions[0].term if suggestions else token
                
                # Skip suggestions that could replace whitelisted terms
                if best.lower() in whitelist and best.lower() != lower_token:
                    best = token  # Keep original to avoid replacing with incorrect whitelist term
                
                if interactive and best.lower() != lower_token:
                    response = input(f"Suggest change: '{token}' → '{best}'? [y/N/q]: ").strip().lower()
                    if response == "q":
                        print("🛑 Exiting interactive session.")
                        exit(0)
                    corrected.append(best if response == "y" else token)
                else:
                    corrected.append(best if best.lower() != token.lower() else token)
        else:
            # Preserve punctuation
            corrected.append(token)
        i += 1
    return corrected

def smart_title_final(tokens, whitelist):
    """
    Apply title casing while preserving whitelist terms exactly.
    """
    # Join tokens preserving punctuation
    text = " ".join(tokens)
    
    # First apply titlecase
    titled = titlecase(text)
    
    # Then fix whitelist items to match their expected casing
    for phrase, correct in whitelist.items():
        # Handle special characters in the whitelist term
        phrase_escaped = re.escape(phrase)
        correct_escaped = re.escape(correct)
        
        # Match any casing of the phrase
        pattern = rf'\b{phrase_escaped}\b'
        titled = re.sub(pattern, correct, titled, flags=re.IGNORECASE)
        
        # Also replace any titlecased version with correct version
        titled = re.sub(rf"\b{re.escape(correct.title())}\b", correct, titled)
    
    return titled

def spell_correct(text: str, whitelist=WHITELIST, sym_spell=sym_spell, interactive=False) -> str:
    """
    Complete spell correction pipeline with structure preservation:
    1. Normalize spacing and remove trailing dots
    2. Tokenize preserving punctuation
    3. Apply corrections to tokens
    4. Apply title casing with whitelist overrides
    5. Final QA check for structural integrity
    """
    # Store original structure for QA comparison
    original = text
    
    # Process through the pipeline
    text = normalize_dots_and_spacing(text)
    tokens = tokenize_with_punctuation(text)
    corrected_tokens = correct_tokens(tokens, whitelist, sym_spell, interactive)
    final = smart_title_final(corrected_tokens, whitelist)
    
    # Strip any trailing whitespace
    final = final.strip()
    
    # QA check - verify structure wasn't damaged
    if not verify_structure_integrity(original, final):
        print(f"⚠️ Warning: Structure mismatch detected")
        print(f"Original: {original}")
        print(f"Cleaned:  {final}")
    
    return final

def verify_structure_integrity(original, cleaned):
    """
    Compare structure of original vs cleaned text to identify regressions.
    Checks punctuation count and positioning.
    """
    # Strip trailing dots from original for fair comparison
    original = re.sub(r"[.]+$", "", original)
    
    # Check punctuation counts (excluding trailing dots)
    orig_punct = [c for c in original if c in ",-/:;()[]{}"]
    clean_punct = [c for c in cleaned if c in ",-/:;()[]{}"]
    
    # Check for major structural differences
    if len(orig_punct) != len(clean_punct):
        return False
    
    # Compare basic whitespace structure (excluding trailing whitespace)
    orig_spaces = [i for i, c in enumerate(original.rstrip()) if c.isspace()]
    clean_spaces = [i for i, c in enumerate(cleaned.rstrip()) if c.isspace()]
    
    # Allow some difference in whitespace count due to normalization
    if abs(len(orig_spaces) - len(clean_spaces)) > 2:
        return False
        
    return True

def load_known_titles(pdf_name):
    known_titles = {}
    if GLOBAL_KNOWN_TITLES.exists():
        with open(GLOBAL_KNOWN_TITLES, 'r') as f:
            known_titles.update(json.load(f))
    pdf_titles = {}
    if LOCAL_KNOWN_TITLES.exists():
        with open(LOCAL_KNOWN_TITLES, 'r') as f:
            pdf_titles.update(json.load(f))
    return known_titles.get(pdf_name, []), pdf_titles

def save_known_titles(pdf_name, pdf_titles):
    LOCAL_KNOWN_TITLES.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_KNOWN_TITLES, 'w') as f:
        json.dump(pdf_titles, f, indent=2)

    all_known = {}
    if GLOBAL_KNOWN_TITLES.exists():
        with open(GLOBAL_KNOWN_TITLES, 'r') as f:
            all_known = json.load(f)
    all_known[pdf_name] = list(pdf_titles.keys())
    with open(GLOBAL_KNOWN_TITLES, 'w') as f:
        json.dump(all_known, f, indent=2)

def main():
    known_list, known_map = load_known_titles(args.pdf_name)

    with open(TOC_INPUT, 'r') as f:
        raw_titles = json.load(f)

    corrected = []
    for title in raw_titles:
        # Keep original for reference
        original_title = title
        
        # Apply normalization
        norm_title = normalize_dots_and_spacing(title)

        # Use known title if available
        if norm_title in known_list:
            fixed = known_map.get(norm_title, norm_title)
        else:
            # Apply spell correction
            fixed = spell_correct(norm_title, interactive=not args.auto)
            
        # Store the corrected title
        corrected.append(fixed)
        known_map[norm_title] = fixed
        
        # Show comparison for verbose output
        if args.interactive and fixed != original_title:
            print(f"Changed: '{original_title}' → '{fixed}'")

    # Save the corrected titles
    with open(TOC_OUTPUT, 'w') as f:
        json.dump(corrected, f, indent=2)

    # Update the known titles database
    save_known_titles(args.pdf_name, known_map)

if __name__ == "__main__":
    main()
