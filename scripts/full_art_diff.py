import zipfile, hashlib, re
from pathlib import Path

BASE = Path("/sessions/rcw-01smbjloedfnae7arot2kk67/mnt/Desktop/dota2-UB")
CURRENT_ZIP = BASE / "mse" / "Dota 2 Universes Beyond.mse-set"
INJECT_ZIP = BASE / "_old_exports" / "new dota 2 set-files" / "set.mse-set"

def parse_blocks(text):
    lines = text.split("\n")
    card_starts = [i for i, l in enumerate(lines) if l == "card:"]
    card_starts.append(len(lines))
    blocks = []
    for idx in range(len(card_starts) - 1):
        blocks.append(lines[card_starts[idx] + 1: card_starts[idx + 1]])
    return blocks

def parse_flat_fields(block):
    """Grab all top-level (single-tab) key: value fields, plus raw styling_data sub-block text."""
    fields = {}
    styling_lines = []
    in_styling = False
    for line in block:
        if line == "\tstyling_data:":
            in_styling = True
            styling_lines = []
            continue
        if in_styling:
            if line.startswith("\t\t"):
                styling_lines.append(line)
                continue
            else:
                in_styling = False
                fields["_styling_data"] = "\n".join(styling_lines)
        if line.startswith("\t") and not line.startswith("\t\t") and ":" in line:
            k, v = line[1:].split(":", 1)
            fields[k] = v.strip()
    if in_styling:
        fields["_styling_data"] = "\n".join(styling_lines)
    return fields

def load_cards(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        with z.open("set") as f:
            text = f.read().decode("utf-8-sig", errors="ignore")
        blocks = parse_blocks(text)
        cards = {}
        for b in blocks:
            f = parse_flat_fields(b)
            name = f.get("name", "").strip()
            if not name:
                continue
            cards[name] = f
        names_in_zip = set(z.namelist())
        return cards, names_in_zip, zip_path

def img_hash(zip_path, names_in_zip, img_ref):
    if not img_ref:
        return None
    candidates = [img_ref, img_ref + ".png"] if not img_ref.endswith(".png") else [img_ref]
    with zipfile.ZipFile(zip_path) as z:
        for cand in candidates:
            if cand in names_in_zip:
                with z.open(cand) as fh:
                    return hashlib.md5(fh.read()).hexdigest()
    return None

cur_cards, cur_names, _ = load_cards(CURRENT_ZIP)
inj_cards, inj_names, _ = load_cards(INJECT_ZIP)

common = sorted(set(cur_cards) & set(inj_cards))
print(f"Comparing {len(common)} cards present in both files...\n")

art_diffs = []
illustrator_diffs = []
styling_diffs = []

img_hash_cache_cur = {}
img_hash_cache_inj = {}

for name in common:
    cf, jf = cur_cards[name], inj_cards[name]

    ci = cf.get("image", "")
    ji = jf.get("image", "")
    if ci not in img_hash_cache_cur:
        img_hash_cache_cur[ci] = img_hash(CURRENT_ZIP, cur_names, ci)
    if ji not in img_hash_cache_inj:
        img_hash_cache_inj[ji] = img_hash(INJECT_ZIP, inj_names, ji)
    ch, jh = img_hash_cache_cur[ci], img_hash_cache_inj[ji]
    if ch != jh:
        art_diffs.append((name, ci, ch, ji, jh))

    cill, jill = cf.get("illustrator", "").strip(), jf.get("illustrator", "").strip()
    if cill != jill:
        illustrator_diffs.append((name, jill, cill))

    csd, jsd = cf.get("_styling_data", ""), jf.get("_styling_data", "")
    if csd != jsd and ch == jh:  # only report styling diff separately if same underlying image (crop-only change)
        styling_diffs.append((name, jsd, csd))

print(f"=== {len(art_diffs)} cards with DIFFERENT embedded art (hash mismatch) ===")
for name, ci, ch, ji, jh in art_diffs:
    print(f"  {name}: current={ci} ({ch}) | aug15={ji} ({jh})")

print()
print(f"=== {len(illustrator_diffs)} cards with different 'illustrator' field ===")
for name, j, c in illustrator_diffs:
    print(f"  {name}: aug15={j!r} -> current={c!r}")

print()
print(f"=== {len(styling_diffs)} cards with SAME art but different crop/styling_data ===")
for name, j, c in styling_diffs:
    print(f"  {name}")
