import os, re, sys, json, glob, hashlib, html
from urllib.parse import quote
from datetime import date
from bs4 import BeautifulSoup, NavigableString, Tag

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import parse_set  # reuse mana/color helpers + build_html/compute_analytics

REPO_DIR = os.path.dirname(SCRIPT_DIR)
SPOILER_DIR = os.path.join(REPO_DIR, "Set Spoiler HTML")
RENDERS_DIR = os.path.join(REPO_DIR, "docs", "renders")
DRAFTMANCER_DIR = os.path.join(REPO_DIR, "Draftmancer TXT")
COCKATRICE_DIR = os.path.join(REPO_DIR, "Cockatrice XML")
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/hlobbdaboss/dota2-UB/main"

# --- locate the current export -------------------------------------------------
html_candidates = glob.glob(os.path.join(SPOILER_DIR, "*.html"))
if not html_candidates:
    raise FileNotFoundError(f"No .html spoiler found in {SPOILER_DIR}")
if len(html_candidates) > 1:
    raise FileNotFoundError(
        f"Multiple .html files in {SPOILER_DIR}: {html_candidates} -- "
        f"keep exactly one export (delete the old one before dropping in a new one)."
    )
SPOILER_HTML = html_candidates[0]
FILES_DIR = SPOILER_HTML[:-5] + "-files"
if not os.path.isdir(FILES_DIR):
    raise FileNotFoundError(f"Expected sibling folder not found: {FILES_DIR}")

print(f"Using spoiler export: {os.path.basename(SPOILER_HTML)}")

with open(SPOILER_HTML, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")


def extract_text(tag):
    """Walk a tag's contents, turning <br> into \\n and <img alt=X> into X,
    concatenating everything else as plain text. Handles the nested
    <span class="symbol"><img alt="W"></span> wrapper used inside rule text."""
    if tag is None:
        return ""
    parts = []

    def walk(node):
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag):
            if node.name == "br":
                parts.append("\n")
            elif node.name == "img":
                parts.append(node.get("alt", ""))
            else:
                for child in node.children:
                    walk(child)

    for child in tag.children:
        walk(child)
    text = html.unescape("".join(parts))
    # Collapse the extra blank line that <br> immediately followed by the
    # source HTML's own pretty-printing newline produces, and trim
    # incidental leading/trailing space on each line.
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


os.makedirs(RENDERS_DIR, exist_ok=True)
# wipe renders dir so a card renamed/removed since the last export doesn't leave
# a stale file lying around under its old name
for fn in os.listdir(RENDERS_DIR):
    fp = os.path.join(RENDERS_DIR, fn)
    if os.path.isfile(fp):
        os.remove(fp)

cards = []
skipped_composites = []

for li in soup.select("li.card"):
    name_span = li.select_one("span.name")
    if not name_span:
        continue
    name = name_span.get_text(strip=True)

    # MSE's HTML export emits an extra composite front+back preview entry for
    # each Battle-type DFC, named "<Front Name> b" -- not a real card, just a
    # side-by-side preview image. Its rule text duplicates the front face's,
    # so keeping it would create a visible duplicate card in the gallery.
    if name.endswith(" b"):
        skipped_composites.append(name)
        continue

    cost_span = li.select_one("span.casting-cost")
    pips = [img.get("alt", "") for img in cost_span.find_all("img")] if cost_span else []
    cost_str = "".join(pips)

    type_span = li.select_one("span.type")
    type_text = type_span.get_text(strip=True) if type_span else ""

    rarity_img = li.select_one("span.rarity img")
    rarity = rarity_img.get("alt", "") if rarity_img else None

    rules = extract_text(li.select_one("span.rule-text"))
    flavor = extract_text(li.select_one("span.flavor-text"))

    pt_span = li.select_one("span.pt")
    pt = pt_span.get_text(strip=True) if pt_span else None

    num_span = li.select_one("span.card-number")
    card_number = num_span.get_text(strip=True) if num_span else None

    link = li.select_one("a[href]")
    img_match = re.search(r"card(\d+)\.jpg$", link["href"]) if link else None
    card_idx = img_match.group(1) if img_match else None

    is_token = "Token" in type_text or "token" in name.lower()

    colors = parse_set.get_color_identity(cost_str, rules)
    card = {
        "name": name,
        "cost": cost_str,
        "type": type_text,
        "rarity": rarity,
        "rules": rules,
        "flavor": flavor,
        "pt": pt,
        "card_number": card_number,
        "cmc": parse_set.cmc_from_cost(cost_str),
        "mana_symbols": pips,
        "colors": colors,
        "color_label": parse_set.color_identity_label(colors),
        "is_token": is_token,
        "_card_idx": card_idx,
    }
    cards.append(card)

print(f"Parsed {len(cards)} cards ({len(skipped_composites)} composite preview entries skipped: {skipped_composites})")

# --- copy renders + hash for cache-busting -------------------------------------
missing_art = []
for c in cards:
    idx = c.pop("_card_idx")
    if not idx:
        missing_art.append(c["name"])
        continue
    src = os.path.join(FILES_DIR, f"card{idx}.jpg")
    if not os.path.isfile(src):
        missing_art.append(c["name"])
        continue
    safe_name = re.sub(r'[\\/:*?"<>|]', "", c["name"])
    render_name = safe_name + ".jpg"
    dst = os.path.join(RENDERS_DIR, render_name)
    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "wb") as f:
        f.write(data)
    c["render"] = render_name
    c["img_ver"] = hashlib.md5(data).hexdigest()[:10]

if missing_art:
    print(f"WARNING: {len(missing_art)} card(s) missing an image: {missing_art}")

# --- write docs/cards.json + docs/index.html (reuse existing builders) --------
analytics = parse_set.compute_analytics(cards)
out_html = parse_set.build_html(cards, analytics)
with open(os.path.join(REPO_DIR, "docs", "index.html"), "w", encoding="utf-8") as f:
    f.write(out_html)
with open(parse_set.OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(cards, f, indent=2, ensure_ascii=False)
print("Wrote docs/index.html and docs/cards.json")

# --- Draftmancer TXT -------------------------------------------------------
os.makedirs(DRAFTMANCER_DIR, exist_ok=True)
for fn in os.listdir(DRAFTMANCER_DIR):
    os.remove(os.path.join(DRAFTMANCER_DIR, fn))

def bracketed_cost(pips):
    return "".join(f"{{{p}}}" for p in pips)

dm_entries = []
for c in cards:
    if c["is_token"]:
        continue
    entry = {
        "name": c["name"],
        "type": c["type"],
        "mana_cost": bracketed_cost(c["mana_symbols"]),
        "rarity": c["rarity"] or "common",
        "oracle_text": c["rules"],
    }
    if c["flavor"]:
        entry["flavor_text"] = c["flavor"]
    if c["pt"]:
        if "/" in c["pt"]:
            entry["power"], entry["toughness"] = c["pt"].split("/", 1)
        else:
            entry["loyalty"] = c["pt"]
    if c.get("render"):
        entry["image"] = f"{GITHUB_RAW_BASE}/docs/renders/{quote(c['render'])}"
    dm_entries.append(entry)

dm_path = os.path.join(DRAFTMANCER_DIR, f"dota-set-draftmancer-{date.today().isoformat()}.txt")
with open(dm_path, "w", encoding="utf-8") as f:
    f.write(f"# Dota 2 Universes Beyond -- Draftmancer custom card list\n")
    f.write(f"# Regenerated {date.today().isoformat()} from the Set Spoiler HTML export.\n")
    f.write(f"# {len(dm_entries)} unique cards.\n\n")
    f.write("[CustomCards]\n")
    f.write(json.dumps(dm_entries, indent=1, ensure_ascii=False))
    f.write("\n")
print(f"Wrote {dm_path} ({len(dm_entries)} cards)")

# --- Cockatrice XML ----------------------------------------------------------
os.makedirs(COCKATRICE_DIR, exist_ok=True)
for fn in os.listdir(COCKATRICE_DIR):
    os.remove(os.path.join(COCKATRICE_DIR, fn))

def xml_escape(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

lines = []
lines.append('<?xml version="1.0" encoding="UTF-8"?>')
lines.append('<cockatrice_carddatabase version="4">')
lines.append(" <sets>")
lines.append("  <set>")
lines.append("   <name>DUB</name>")
lines.append("   <longname>Dota 2 Universes Beyond</longname>")
lines.append("   <settype>Custom</settype>")
lines.append(f"   <releasedate>{date.today().isoformat()}</releasedate>")
lines.append("  </set>")
lines.append(" </sets>")
lines.append(" <cards>")
row = 0
ck_count = 0
for c in cards:
    if c["is_token"]:
        continue
    row += 1
    ck_count += 1
    maintype = c["type"].split(" — ")[0].split()[-1] if c["type"] else ""
    lines.append("  <card>")
    lines.append(f"   <name>{xml_escape(c['name'])}</name>")
    lines.append(f"   <text>{xml_escape(c['rules'])}</text>")
    lines.append("   <prop>")
    lines.append("   <layout>normal</layout>")
    lines.append("   <side>front</side>")
    lines.append(f"   <type>{xml_escape(c['type'])}</type>")
    lines.append(f"   <maintype>{xml_escape(maintype)}</maintype>")
    bc = bracketed_cost(c["mana_symbols"])
    if bc:
        lines.append(f"   <manacost>{xml_escape(bc)}</manacost>")
    lines.append(f"   <cmc>{c['cmc']}</cmc>")
    if c["colors"]:
        lines.append(f"   <colors>{''.join(c['colors'])}</colors>")
        lines.append(f"   <coloridentity>{''.join(c['colors'])}</coloridentity>")
    if c["pt"]:
        if "/" in c["pt"]:
            lines.append(f"   <pt>{xml_escape(c['pt'])}</pt>")
        else:
            lines.append(f"   <loyalty>{xml_escape(c['pt'])}</loyalty>")
    lines.append("   </prop>")
    picurl = f"{GITHUB_RAW_BASE}/docs/renders/{quote(c['render'])}" if c.get("render") else ""
    num = c["card_number"] or f"{row:04d}"
    lines.append(f'   <set rarity="{xml_escape(c["rarity"] or "common")}" num="{xml_escape(num)}" picurl="{xml_escape(picurl)}">DUB</set>')
    lines.append(f"   <tablerow>{row}</tablerow>")
    lines.append("  </card>")
lines.append(" </cards>")
lines.append("</cockatrice_carddatabase>")

ck_path = os.path.join(COCKATRICE_DIR, f"Dota2UniversesBeyond-cockatrice-{date.today().isoformat()}.xml")
with open(ck_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"Wrote {ck_path} ({ck_count} cards)")

print("DONE -- no git commands run")
