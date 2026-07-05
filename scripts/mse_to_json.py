#!/usr/bin/env python3
"""
mse_to_json.py

Converts a Magic Set Editor (.mse-set) file into the cards.json format used
by the Dota 2 Universes Beyond website.

Usage:
    python3 mse_to_json.py path/to/Dota_Set.mse-set path/to/output/cards.json

The .mse-set file is a zip archive containing:
  - a plain-text file called "set" with all card data (indented key:value format)
  - the embedded card artwork images referenced by each card

This script:
  1. Unzips the .mse-set into a temp folder
  2. Parses the "set" file into per-card records
  3. Cleans up MSE's internal markup tags (e.g. <kw-a>, <i-auto>, <word-list-*>)
  4. Derives cmc / mana_symbols / colors / color_label from the casting cost
  5. Computes img_ver as the first 10 hex chars of the MD5 hash of each card's image
  6. Writes out cards.json matching the existing schema
"""

import sys
import re
import json
import zipfile
import hashlib
import tempfile
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WUBRG_ORDER = "WUBRG"

COLOR_NAMES = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
}

GUILD_NAMES = {
    frozenset("WU"): "Azorius",
    frozenset("UB"): "Dimir",
    frozenset("BR"): "Rakdos",
    frozenset("RG"): "Gruul",
    frozenset("GW"): "Selesnya",
    frozenset("WB"): "Orzhov",
    frozenset("UR"): "Izzet",
    frozenset("BG"): "Golgari",
    frozenset("RW"): "Boros",
    frozenset("GU"): "Simic",
}

# Fields that hold potentially multi-line "block scalar" text in the MSE format
TEXT_BLOCK_FIELDS = {"rule_text", "rule_text_2", "flavor_text", "flavor_text_2"}

# Fields we don't care about and should just skip over (including any nested
# indented children, e.g. styling_data: { ... })
SKIP_NESTED_FIELDS = {"styling_data", "extra_data"}

# Tag-stripping regex: MSE stores rich text as pseudo-XML tags like
# <kw-a>, <i-auto>, <word-list-type-en>, <error-spelling:en_US:...>, etc.
# We simply drop all tags and keep the inner text.
TAG_RE = re.compile(r"<[^>]*>")


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Step 1: Parse the "set" file into a list of raw per-card field dicts
# ---------------------------------------------------------------------------

def parse_set_file(set_path: Path):
    with open(set_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    # strip only the newline, keep leading tabs intact
    lines = [line.rstrip("\n").rstrip("\r") for line in lines]

    # Find all top-level (0-indent) "card:" line indices
    card_starts = [i for i, line in enumerate(lines) if line == "card:"]
    card_starts.append(len(lines))  # sentinel end

    cards_raw = []
    for idx in range(len(card_starts) - 1):
        start = card_starts[idx] + 1
        end = card_starts[idx + 1]
        block = lines[start:end]
        cards_raw.append(parse_card_block(block))
    return cards_raw


def parse_card_block(block_lines):
    """Parse a single card's lines (already excluding the 'card:' header line)
    into a dict of {field_name: value}. Only fields at 1-tab indentation are
    captured as top-level; text-block fields spanning multiple deeper-indented
    lines are joined with '\n'.
    """
    fields = {}
    i = 0
    n = len(block_lines)
    while i < n:
        line = block_lines[i]
        if line == "":
            i += 1
            continue
        # Must be exactly 1-tab indented to be a top-level field of this card
        if not line.startswith("\t") or line.startswith("\t\t"):
            i += 1
            continue
        content = line[1:]  # strip the single leading tab
        if ":" not in content:
            i += 1
            continue
        key, _, inline_val = content.partition(":")
        inline_val = inline_val.strip()

        if key in SKIP_NESTED_FIELDS:
            # consume all deeper-indented lines that follow (ignore them)
            i += 1
            while i < n and (block_lines[i].startswith("\t\t") or block_lines[i] == ""):
                i += 1
            continue

        if key in TEXT_BLOCK_FIELDS:
            text_lines = []
            if inline_val:
                text_lines.append(inline_val)
                i += 1
            else:
                i += 1
                while i < n and (block_lines[i].startswith("\t\t") or block_lines[i] == ""):
                    if block_lines[i] != "":
                        text_lines.append(block_lines[i][2:])  # strip 2 leading tabs
                    i += 1
            fields[key] = "\n".join(strip_tags(t) for t in text_lines).strip()
            continue

        # Generic scalar field (possibly with nested lines we don't need,
        # e.g. some multi-line super_type variants) -- just take inline value
        # and skip any deeper-indented continuation lines.
        fields[key] = strip_tags(inline_val)
        i += 1
        while i < n and (block_lines[i].startswith("\t\t") or block_lines[i] == ""):
            i += 1

    return fields


# ---------------------------------------------------------------------------
# Step 2: Mana cost tokenizing / cmc / colors
# ---------------------------------------------------------------------------

MANA_SYMBOL_RE = re.compile(r"\d+|X|[WUBRG]/[WUBRG]|[WUBRG]")


def tokenize_cost(cost: str):
    """Turn a raw casting_cost string like '2WU' or '1B/RB/R' or 'XXBR'
    into a list of symbol tokens, matching the site's existing convention:
      - generic numbers stay as-is ('2')
      - hybrid pairs lose the slash ('B/R' -> 'BR')
      - single colored/X symbols stay as-is
    """
    tokens = []
    for m in MANA_SYMBOL_RE.finditer(cost):
        tok = m.group(0)
        if "/" in tok:
            tok = tok.replace("/", "")
        tokens.append(tok)
    return tokens


def compute_cmc(tokens):
    total = 0
    for t in tokens:
        if t.isdigit():
            total += int(t)
        elif t == "X":
            total += 0
        else:
            # single color (e.g. 'W') or hybrid pair (e.g. 'BR') both count as 1
            total += 1
    return total


def compute_colors(tokens):
    found = set()
    for t in tokens:
        if t.isdigit() or t == "X":
            continue
        for ch in t:
            found.add(ch)
    return sorted(found, key=lambda c: WUBRG_ORDER.index(c))


def compute_color_label(colors):
    n = len(colors)
    if n == 0:
        return "Colorless"
    if n == 1:
        return COLOR_NAMES[colors[0]]
    if n == 2:
        return GUILD_NAMES.get(frozenset(colors), f"{n}-color")
    return f"{n}-color"


# ---------------------------------------------------------------------------
# Step 3: Build the final card record matching the site's cards.json schema
# ---------------------------------------------------------------------------

def normalize_image_name(raw_image: str) -> str:
    raw_image = raw_image.strip()
    if not raw_image:
        return ""
    if not raw_image.lower().endswith(".png"):
        raw_image += ".png"
    return raw_image


def build_card_record(raw, extracted_dir: Path):
    out = {}
    out["name"] = raw.get("name", "").strip()

    has_cost_key = "casting_cost" in raw
    cost_val = raw.get("casting_cost", "")
    if has_cost_key:
        out["cost"] = cost_val

    image_name = normalize_image_name(raw.get("image", ""))
    out["image"] = image_name

    super_type = raw.get("super_type", "").strip()
    sub_type = raw.get("sub_type", "").strip()
    out["super_type"] = super_type
    out["sub_type"] = sub_type

    if "rarity" in raw and raw["rarity"].strip():
        out["rarity"] = raw["rarity"].strip()

    has_rule_key = "rule_text" in raw or "rule_text_2" in raw
    if has_rule_key:
        rule_parts = [p for p in (raw.get("rule_text", ""), raw.get("rule_text_2", "")) if p]
        out["rules"] = "\n".join(rule_parts).strip()

    has_flavor_key = "flavor_text" in raw or "flavor_text_2" in raw
    if has_flavor_key:
        flavor_parts = [p for p in (raw.get("flavor_text", ""), raw.get("flavor_text_2", "")) if p]
        out["flavor"] = "\n".join(flavor_parts).strip()

    if sub_type:
        out["type"] = f"{super_type} -- {sub_type}"
    else:
        out["type"] = super_type

    tokens = tokenize_cost(cost_val) if has_cost_key else []
    out["cmc"] = compute_cmc(tokens)
    out["mana_symbols"] = tokens
    colors = compute_colors(tokens)
    out["colors"] = colors
    out["color_label"] = compute_color_label(colors)

    out["is_token"] = "Token" in super_type

    # img_ver: hash whichever actual extracted file matches, trying the
    # exact filename first, then the extensionless version.
    img_ver = compute_img_ver(raw.get("image", ""), image_name, extracted_dir)
    if img_ver:
        out["img_ver"] = img_ver

    return out


def compute_img_ver(raw_image_ref: str, normalized_name: str, extracted_dir: Path):
    candidates = []
    if normalized_name:
        candidates.append(extracted_dir / normalized_name)
    if raw_image_ref:
        candidates.append(extracted_dir / raw_image_ref.strip())
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            h = hashlib.md5(candidate.read_bytes()).hexdigest()
            return h[:10]
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 mse_to_json.py <input.mse-set> <output cards.json>")
        sys.exit(1)

    mse_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(mse_path, "r") as zf:
            zf.extractall(tmp_path)

        set_file = tmp_path / "set"
        if not set_file.exists():
            print("ERROR: could not find 'set' file inside the archive.")
            sys.exit(1)

        raw_cards = parse_set_file(set_file)
        cards = [build_card_record(raw, tmp_path) for raw in raw_cards]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(cards)} cards to {out_path}")


if __name__ == "__main__":
    main()
