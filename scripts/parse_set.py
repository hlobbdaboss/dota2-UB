cat << 'EOF' > parse_set.py
import zipfile
import json
import os
import subprocess
from datetime import datetime
import re

# Paths
MSE_FILE = "/Users/Harrison_1/Desktop/Full-Magic-Pack-main/Sets/Dota Set.mse-set"
REPO_DIR = "/Users/Harrison_1/dota2-set"
OUTPUT_JSON = os.path.join(REPO_DIR, "docs", "cards.json")
IMAGES_DIR = os.path.join(REPO_DIR, "docs", "cards")

# ─── Mana parsing ─────────────────────────────────────────────────────────────

def parse_mana_cost(cost_str):
    if not cost_str:
        return []
    tokens = []
    i = 0
    s = cost_str.strip().replace(" ", "").upper()
    while i < len(s):
        if i + 2 < len(s) and s[i+1] == '/':
            tokens.append(s[i:i+3]); i += 3
        elif i + 3 < len(s) and s[i+2] == '/':
            tokens.append(s[i:i+4]); i += 4
        elif s[i].isdigit():
            j = i
            while j < len(s) and s[j].isdigit(): j += 1
            tokens.append(s[i:j]); i = j
        elif s[i] == 'X':
            tokens.append('X'); i += 1
        elif s[i].isalpha():
            tokens.append(s[i]); i += 1
        else:
            i += 1
    return tokens


def pip_to_scryfall(pip):
    pip = pip.upper()
    if '/' in pip:
        parts = pip.split('/')
        order = 'WUBRG'
        colored = [p for p in parts if p in order]
        other = [p for p in parts if p not in order]
        sorted_parts = sorted(colored, key=lambda c: order.index(c) if c in order else 99) + other
        return ''.join(sorted_parts)
    return pip


def mana_symbols_list(cost_str):
    return [pip_to_scryfall(p) for p in parse_mana_cost(cost_str)]


def cmc_from_cost(cost_str):
    total = 0
    for pip in parse_mana_cost(cost_str):
        if pip == 'X': continue
        elif '/' in pip: total += 1
        elif re.match(r'^\d+$', pip): total += int(pip)
        else: total += 1
    return total


# ─── Color identity ───────────────────────────────────────────────────────────

def get_color_identity(cost_str, rules_text=''):
    pips = parse_mana_cost(cost_str)
    colors = set()
    for pip in pips:
        for ch in pip:
            if ch in 'WUBRG':
                colors.add(ch)
    for ch in 'WUBRG':
        if '{' + ch + '}' in rules_text:
            colors.add(ch)
    return sorted(colors, key=lambda c: 'WUBRG'.index(c))


def color_identity_label(colors):
    key = ''.join(colors)
    labels = {
        '': 'Colorless', 'W': 'White', 'U': 'Blue', 'B': 'Black',
        'R': 'Red', 'G': 'Green',
        'WU': 'Azorius', 'WB': 'Orzhov', 'WR': 'Boros', 'WG': 'Selesnya',
        'UB': 'Dimir', 'UR': 'Izzet', 'UG': 'Simic',
        'BR': 'Rakdos', 'BG': 'Golgari', 'RG': 'Gruul',
    }
    return labels.get(key, f'{len(colors)}-color' if colors else 'Colorless')


# ─── Text cleanup ─────────────────────────────────────────────────────────────

def clean_mse_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\\n', '\n')
    return text.strip()


# ─── MSE parser ───────────────────────────────────────────────────────────────

def parse_mse(filepath):
    with zipfile.ZipFile(filepath, 'r') as z:
        print("Extracting card images...")
        os.makedirs(IMAGES_DIR, exist_ok=True)
        for name in z.namelist():
            if name.endswith('.png'):
                with z.open(name) as img_file:
                    out_path = os.path.join(IMAGES_DIR, name)
                    with open(out_path, 'wb') as f:
                        f.write(img_file.read())
        with z.open('set') as f:
            content = f.read().decode('utf-8', errors='ignore')

    cards = []
    blocks = content.split('\ncard:\n')

    for block in blocks[1:]:
        card = {}
        lines = block.splitlines()
        current_field = None
        current_value = []

        for line in lines:
            s = line.strip()
            def field_val(prefix): return s[len(prefix):].strip()

            if s.startswith('name:'):
                card['name'] = field_val('name:'); current_field = None
            elif s.startswith('casting_cost:'):
                card['cost'] = field_val('casting_cost:'); current_field = None
            elif s.startswith('image:') and 'image_2' not in s and 'image_3' not in s:
                val = field_val('image:')
                if val:
                    card['image'] = val if val.endswith('.png') else val + '.png'
                current_field = None
            elif s.startswith('super_type:'):
                card['super_type'] = clean_mse_text(field_val('super_type:')); current_field = None
            elif s.startswith('sub_type:'):
                card['sub_type'] = clean_mse_text(field_val('sub_type:')); current_field = None
            elif s.startswith('rarity:'):
                card['rarity'] = field_val('rarity:'); current_field = None
            elif s.startswith('rule_text:'):
                if current_field and current_value:
                    card[current_field] = '\n'.join(current_value).strip()
                current_field = 'rules'
                current_value = [clean_mse_text(field_val('rule_text:'))]
            elif s.startswith('flavor_text:'):
                if current_field and current_value:
                    card[current_field] = '\n'.join(current_value).strip()
                current_field = 'flavor'
                current_value = [clean_mse_text(field_val('flavor_text:'))]
            elif s.startswith('pt:'):
                if current_field and current_value:
                    card[current_field] = '\n'.join(current_value).strip()
                card['pt'] = field_val('pt:'); current_field = None
            elif current_field and s and ':' not in s[:20]:
                current_value.append(clean_mse_text(s))

        if current_field and current_value:
            card[current_field] = '\n'.join(current_value).strip()

        if 'name' in card and card['name']:
            super_type = card.get('super_type', '')
            sub_type = card.get('sub_type', '')
            card['type'] = f"{super_type} — {sub_type}" if sub_type else super_type
            card['cmc'] = cmc_from_cost(card.get('cost', ''))
            card['mana_symbols'] = mana_symbols_list(card.get('cost', ''))
            card['colors'] = get_color_identity(card.get('cost', ''), card.get('rules', ''))
            card['color_label'] = color_identity_label(card['colors'])
            card['is_token'] = 'Token' in card.get('type', '') or 'token' in card.get('name', '').lower()
            cards.append(card)

    return cards


# ─── Analytics ────────────────────────────────────────────────────────────────

def compute_analytics(cards):
    playable = [c for c in cards if not c.get('is_token') and c.get('name')]
    color_counts = {k: 0 for k in ['White','Blue','Black','Red','Green',
        'Azorius','Orzhov','Boros','Selesnya','Dimir','Izzet','Simic',
        'Rakdos','Golgari','Gruul','Colorless','Land']}
    cmc_counts = {i: 0 for i in range(10)}
    type_counts = {'Creature':0,'Instant':0,'Sorcery':0,'Enchantment':0,'Artifact':0,'Land':0,'Other':0}

    for c in playable:
        t = c.get('type', '')
        label = c.get('color_label', 'Colorless')
        if 'Land' in t:
            color_counts['Land'] += 1
        else:
            color_counts[label] = color_counts.get(label, 0) + 1
        cmc_counts[min(c.get('cmc', 0), 9)] += 1
        if 'Land' in t: type_counts['Land'] += 1
        elif 'Creature' in t: type_counts['Creature'] += 1
        elif 'Instant' in t: type_counts['Instant'] += 1
        elif 'Sorcery' in t: type_counts['Sorcery'] += 1
        elif 'Enchantment' in t: type_counts['Enchantment'] += 1
        elif 'Artifact' in t: type_counts['Artifact'] += 1
        else: type_counts['Other'] += 1

    return {'total': len(playable), 'color_counts': color_counts,
            'cmcC': cmc_counts, 'type_counts': type_counts}


# ─── HTML builder ─────────────────────────────────────────────────────────────

def build_html(cards, analytics):
    cards_json = json.dumps(cards, ensure_ascii=False)
    analytics_json = json.dumps(analytics, ensure_ascii=False)

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <title>Dota 2 Cube — Universes Beyond</title>\n'
        '  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n'
        '  <style>\n'
        '    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\n'
        '    body { background: #0d0f1a; color: #e8e0d0; font-family: Georgia, serif; min-height: 100vh; }\n'
        '    .header { background: linear-gradient(180deg,#1a1228 0%,#0d0f1a 100%); border-bottom: 1px solid #c89b3c44; padding: 28px 24px 20px; text-align: center; }\n'
        '    .header h1 { font-size: 2.8em; color: #c89b3c; letter-spacing: .04em; text-shadow: 0 0 40px #c89b3c66; margin-bottom: 4px; }\n'
        '    .header .tagline { color: #7a7060; font-size: .95em; letter-spacing: .08em; text-transform: uppercase; }\n'
        '    .dashboard { display: grid; grid-template-columns: 140px 1fr 1fr 1fr; gap: 12px; padding: 16px 20px; background: #111420; border-bottom: 1px solid #c89b3c22; }\n'
        '    .stat-box { background: #1a1e30; border: 1px solid #c89b3c33; border-radius: 8px; padding: 16px; display: flex; flex-direction: column; align-items: center; justify-content: center; }\n'
        '    .stat-number { font-size: 3em; font-weight: bold; color: #c89b3c; line-height: 1; }\n'
        '    .stat-label { font-size: .7em; color: #7a7060; text-transform: uppercase; letter-spacing: .1em; margin-top: 6px; }\n'
        '    .chart-box { background: #1a1e30; border: 1px solid #c89b3c33; border-radius: 8px; padding: 12px; }\n'
        '    .chart-title { font-size: .72em; color: #7a7060; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }\n'
        '    .chart-box canvas { max-height: 120px; cursor: pointer; }\n'
        '    .filters { display: flex; flex-wrap: wrap; gap: 10px; padding: 14px 20px; background: #0d0f1a; border-bottom: 1px solid #c89b3c22; align-items: center; }\n'
        '    .filters input, .filters select { background: #1a1e30; border: 1px solid #c89b3c44; color: #e8e0d0; padding: 7px 12px; border-radius: 6px; font-size: .85em; font-family: Georgia,serif; }\n'
        '    .filters input { width: 220px; }\n'
        '    .filters select { cursor: pointer; }\n'
        '    .filters input:focus, .filters select:focus { outline: none; border-color: #c89b3c; }\n'
        '    .reset-btn { background: #c89b3c; color: #0d0f1a; border: none; padding: 7px 16px; border-radius: 6px; font-size: .85em; font-weight: bold; cursor: pointer; font-family: Georgia,serif; margin-left: auto; }\n'
        '    .reset-btn:hover { background: #e0b44e; }\n'
        '    .result-count { font-size: .8em; color: #7a7060; white-space: nowrap; }\n'
        '    .grid { display: flex; flex-wrap: wrap; gap: 10px; padding: 16px 20px; justify-content: flex-start; }\n'
        '    .card { width: 160px; height: 232px; cursor: pointer; transition: transform .15s,box-shadow .15s; border-radius: 8px; overflow: hidden; background: #12151f; border: 1px solid #c89b3c22; display: flex; flex-direction: column; }\n'
        '    .card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(200,155,60,.25); border-color: #c89b3c88; }\n'
        '    .card .img-container { width: 100%; aspect-ratio: 5/7; background: #12151f; overflow: hidden; position: relative; flex: 1; }\n'
        '    .card img { width: 100%; height: 100%; object-fit: cover; display: block; }\n'
        '    .card .no-img { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: #12151f; color: #3a3520; font-size: 2em; }\n'
        '    .card-footer { padding: 6px 8px; display: flex; align-items: center; justify-content: space-between; gap: 4px; background: #1a1e30; border-top: 1px solid #c89b3c11; }\n'
        '    .card-name { font-size: .68em; color: #c89b3c; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }\n'
        '    .rarity-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }\n'
        '    .r-common { background: #999; } .r-uncommon { background: #6aadff; } .r-rare { background: #ffaa44; } .r-mythic { background: #ff66aa; }\n'
        '    .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.88); z-index: 200; justify-content: center; align-items: center; padding: 20px; }\n'
        '    .modal.active { display: flex; }\n'
        '    .modal-inner { background: #1a1e30; border: 1px solid #c89b3c66; border-radius: 12px; max-width: 480px; width: 100%; max-height: 90vh; overflow-y: auto; position: relative; padding: 20px; }\n'
        '    .modal-close { position: absolute; top: 12px; right: 16px; font-size: 1.4em; cursor: pointer; color: #7a7060; background: none; border: none; line-height: 1; }\n'
        '    .modal-close:hover { color: #e8e0d0; }\n'
        '    .modal img { width: 100%; border-radius: 8px; margin-bottom: 14px; }\n'
        '    .modal-name { font-size: 1.3em; color: #c89b3c; margin-bottom: 4px; }\n'
        '    .modal-cost { display: flex; flex-direction: row; align-items: center; flex-wrap: wrap; gap: 2px; margin-bottom: 8px; line-height: 1; }\n'
        '    .modal-cost img { width: 22px; height: 22px; border-radius: 50%; box-shadow: 0 1px 3px rgba(0,0,0,.6); display: inline-block; vertical-align: middle; }\n'
        '    .modal-type { font-size: .85em; color: #7a7060; font-style: italic; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #c89b3c22; }\n'
        '    .modal-rules { font-size: .88em; line-height: 1.65; margin-bottom: 10px; white-space: pre-line; }\n'
        '    .modal-rules img { width: 15px; height: 15px; vertical-align: -2px; display: inline-block; margin: 0 1px; }\n'
        '    .modal-flavor { font-size: .8em; color: #7a7060; font-style: italic; border-top: 1px solid #c89b3c22; padding-top: 10px; line-height: 1.5; }\n'
        '    .modal-pt { text-align: right; font-size: 1.1em; font-weight: bold; color: #c89b3c; margin-top: 8px; }\n'
        '    .modal-meta { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }\n'
        '    .badge { font-size: .7em; padding: 2px 8px; border-radius: 20px; background: #0d0f1a; border: 1px solid #c89b3c44; color: #c89b3c; text-transform: uppercase; letter-spacing: .06em; }\n'
        '  </style>\n'
        '</head>\n'
        '<body>\n'
        '<div class="header">\n'
        '  <h1>Dota 2 Cube</h1>\n'
        '  <div class="tagline">Universes Beyond &nbsp;&middot;&nbsp; Custom Design Portfolio</div>\n'
        '</div>\n'
        '<div class="dashboard">\n'
        '  <div class="stat-box"><div class="stat-number" id="displayed-count">0</div><div class="stat-label" id="kpiLabel">Draft Cards</div></div>\n'
        '  <div class="chart-box"><div class="chart-title">Color Identity Distribution</div><canvas id="colorChart"></canvas></div>\n'
        '  <div class="chart-box"><div class="chart-title">Mana Curve</div><canvas id="cmcChart"></canvas></div>\n'
        '  <div class="chart-box"><div class="chart-title">Card Types</div><canvas id="typeChart"></canvas></div>\n'
        '</div>\n'
        '<div class="filters">\n'
        '  <input type="text" id="search" placeholder="Search name or text&hellip;" oninput="applyFilters()">\n'
        '  <select id="color-filter" onchange="applyFilters()">\n'
        '    <option value="">All Colors</option>\n'
        '    <option value="White">White</option><option value="Blue">Blue</option>\n'
        '    <option value="Black">Black</option><option value="Red">Red</option>\n'
        '    <option value="Green">Green</option>\n'
        '    <option value="Azorius">Azorius (WU)</option><option value="Orzhov">Orzhov (WB)</option>\n'
        '    <option value="Boros">Boros (WR)</option><option value="Selesnya">Selesnya (WG)</option>\n'
        '    <option value="Dimir">Dimir (UB)</option><option value="Izzet">Izzet (UR)</option>\n'
        '    <option value="Simic">Simic (UG)</option><option value="Rakdos">Rakdos (BR)</option>\n'
        '    <option value="Golgari">Golgari (BG)</option><option value="Gruul">Gruul (RG)</option>\n'
        '    <option value="Colorless">Colorless</option>\n'
        '  </select>\n'
        '  <select id="type-filter" onchange="applyFilters()">\n'
        '    <option value="">All Types</option>\n'
        '    <option value="Creature">Creature</option><option value="Instant">Instant</option>\n'
        '    <option value="Sorcery">Sorcery</option><option value="Enchantment">Enchantment</option>\n'
        '    <option value="Artifact">Artifact</option><option value="Land">Land</option>\n'
        '  </select>\n'
        '  <select id="rarity-filter" onchange="applyFilters()">\n'
        '    <option value="">All Rarities</option>\n'
        '    <option value="common">Common</option><option value="uncommon">Uncommon</option>\n'
        '    <option value="rare">Rare</option><option value="mythic rare">Mythic</option>\n'
        '  </select>\n'
        '  <select id="cmc-filter" onchange="applyFilters()">\n'
        '    <option value="">All CMC</option>\n'
        '    <option value="0">0</option><option value="1">1</option><option value="2">2</option>\n'
        '    <option value="3">3</option><option value="4">4</option><option value="5">5</option>\n'
        '    <option value="6">6+</option>\n'
        '  </select>\n'
        '  <select id="variant-filter" onchange="applyFilters()">\n'
        '    <option value="All">All Cube Cards</option>\n'
        '    <option value="Token">Tokens Only</option>\n'
        '  </select>\n'
        '  <select id="sort-filter" onchange="applyFilters()">\n'
        '    <option value="name">Name (A&ndash;Z)</option>\n'
        '    <option value="cmc">Mana Value</option><option value="color">Color</option>\n'
        '    <option value="rarity">Rarity</option><option value="type">Type</option>\n'
        '  </select>\n'
        '  <span class="result-count" id="result-count"></span>\n'
        '  <button class="reset-btn" onclick="resetFilters()">Reset Filters</button>\n'
        '</div>\n'
        '<div class="grid" id="grid"></div>\n'
        '<div class="modal" id="modal" onclick="modalBgClick(event)">\n'
        '  <div class="modal-inner">\n'
        '    <button class="modal-close" onclick="closeModal()">&times;</button>\n'
        '    <div id="modal-body"></div>\n'
        '  </div>\n'
        '</div>\n'
        '<script>\n'
        'const ALL_CARDS = ' + cards_json + ';\n'
        'const ANALYTICS = ' + analytics_json + ';\n'
        'let chart1, chart2, chart3;\n'
        'let visibleCards = [];\n'
        '\n'
        'const SCRYFALL = "https://svgs.scryfall.io/card-symbols/";\n'
        '\n'
        'function manaImg(sym) {\n'
        '  return `<img src="${SCRYFALL}${sym}.svg" style="width:22px;height:22px;border-radius:50%;box-shadow:0 1px 3px rgba(0,0,0,.6);vertical-align:middle;display:inline-block;" title="{${sym}}">`;\n'
        '}\n'
        '\n'
        'function formatCost(syms) {\n'
        '  if (!syms || !syms.length) return "";\n'
        '  return syms.map(manaImg).join("");\n'
        '}\n'
        '\n'
        'function rarityClass(r) {\n'
        '  if (!r) return "r-common";\n'
        '  const rl = r.toLowerCase();\n'
        '  if (rl.includes("mythic")) return "r-mythic";\n'
        '  if (rl === "rare") return "r-rare";\n'
        '  if (rl === "uncommon") return "r-uncommon";\n'
        '  return "r-common";\n'
        '}\n'
        '\n'
        'function rarityOrder(r) {\n'
        '  if (!r) return 0;\n'
        '  const rl = r.toLowerCase();\n'
        '  if (rl.includes("mythic")) return 3;\n'
        '  if (rl === "rare") return 2;\n'
        '  if (rl === "uncommon") return 1;\n'
        '  return 0;\n'
        '}\n'
        '\n'
        'function applyFilters() {\n'
        '  const q   = document.getElementById("search").value.toLowerCase();\n'
        '  const col = document.getElementById("color-filter").value;\n'
        '  const typ = document.getElementById("type-filter").value;\n'
        '  const rar = document.getElementById("rarity-filter").value;\n'
        '  const cmc = document.getElementById("cmc-filter").value;\n'
        '  const vrnt = document.getElementById("variant-filter").value;\n'
        '  const srt = document.getElementById("sort-filter").value;\n'
        '\n'
        '  let filtered = ALL_CARDS.filter(c => {\n'
        '    const nm = !q || (c.name||"").toLowerCase().includes(q) || (c.rules||"").toLowerCase().includes(q);\n'
        '    const cm = !col || c.color_label === col;\n'
        '    const tm = !typ || (c.type||"").includes(typ);\n'
        '    const rm = !rar || (c.rarity||"").toLowerCase() === rar;\n'
        '    const mm = !cmc || (cmc==="6" ? c.cmc>=6 : c.cmc==parseInt(cmc));\n'
        '    const vm = vrnt==="Token" ? c.is_token : !c.is_token;\n'
        '    return nm && cm && tm && rm && mm && vm;\n'
        '  });\n'
        '\n'
        '  filtered.sort((a,b) => {\n'
        '    if (srt==="name")   return (a.name||"").localeCompare(b.name||"");\n'
        '    if (srt==="cmc")    return (a.cmc||0)-(b.cmc||0) || (a.name||"").localeCompare(b.name||"");\n'
        '    if (srt==="color")  return (a.color_label||"").localeCompare(b.color_label||"") || (a.name||"").localeCompare(b.name||"");\n'
        '    if (srt==="rarity") return rarityOrder(b.rarity)-rarityOrder(a.rarity) || (a.name||"").localeCompare(b.name||"");\n'
        '    if (srt==="type")   return (a.type||"").localeCompare(b.type||"") || (a.name||"").localeCompare(b.name||"");\n'
        '    return 0;\n'
        '  });\n'
        '\n'
        '  visibleCards = filtered;\n'
        '  renderGrid(filtered);\n'
        '  document.getElementById("result-count").textContent = filtered.length + " of " + ALL_CARDS.length + " cards";\n'
        '  document.getElementById("displayed-count").textContent = filtered.length;\n'
        '  document.getElementById("kpiLabel").textContent = vrnt==="Token" ? "Tokens" : "Draft Cards";\n'
        '  updateCharts(filtered);\n'
        '}\n'
        '\n'
        'function resetFilters() {\n'
        '  ["search"].forEach(id => document.getElementById(id).value = "");\n'
        '  ["color-filter","type-filter","rarity-filter","cmc-filter","sort-filter"].forEach(id => document.getElementById(id).value = "");\n'
        '  document.getElementById("variant-filter").value = "All";\n'
        '  document.getElementById("sort-filter").value = "name";\n'
        '  applyFilters();\n'
        '}\n'
        '\n'
        'function renderGrid(cards) {\n'
        '  document.getElementById("grid").innerHTML = cards.map((c,i) => {\n'
        '    const imgHtml = c.image\n'
        '      ? `<img src="cards/${c.image}" alt="${c.name}" loading="lazy" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';">`\n'
        '      : "";\n'
        '    const displayNoImg = c.image ? "none" : "flex";\n'
        '    return `<div class="card" onclick="showModal(${i})">` +\n'
        '             `<div class="img-container">${imgHtml}<div class="no-img" style="display:${displayNoImg}">🎴</div></div>` +\n'
        '             `<div class="card-footer"><span class="card-name">${c.name}</span><span class="rarity-dot ${rarityClass(c.rarity)}"></span></div>` +\n'
        '           `</div>`;\n'
        '  }).join("");\n'
        '}\n'
        '\n'
        'function renderRulesSymbols(text) {\n'
        '  if (!text) return "";\n'
        '  const WUBRG = "WUBRG";\n'
        '\n'
        '  // 1. Parse complex multi-slash hybrid symbols (like R/W/P or R/W/B) dynamically\n'
        '  text = text.replace(/([WUBRGC0-9])(\\\/[WUBRGCP])+/gi, (match) => {\n'
        '    const parts = match.toUpperCase().split("/");\n'
        '    const colored = parts.filter(p => WUBRG.includes(p));\n'
        '    const other = parts.filter(p => !WUBRG.includes(p));\n'
        '    const sortedSym = sortedSym = colored.sort((a, b) => WUBRG.indexOf(a) - WUBRG.indexOf(b)).join("") + other.join("");\n'
        '    return `<img src="${SCRYFALL}${sortedSym}.svg">`;\n'
        '  });\n'
        '\n'
        '  // 2. Parse remaining standard single slash hybrid tokens\n'
        '  text = text.replace(/([WUBRGC2])\\\/([WUBRGCP])/gi, (m, a, b) => {\n'
        '    a = a.toUpperCase(); b = b.toUpperCase();\n'
        '    let sym = (a === "2" || a === "P") ? a + b : (WUBRG.indexOf(a) <= WUBRG.indexOf(b) ? a + b : b + a);\n'
        '    return `<img src="${SCRYFALL}${sym}.svg">`;\n'
        '  });\n'
        '\n'
        '  // 3. Swap T symbol entries directly into Scryfall tap icon paths\n'
        '  text = text.replace(/\\bT\\b(?![\\/<])/g, `<img src="${SCRYFALL}T.svg" title="Tap">`);\n'
        '\n'
        '  // 4. Parse isolated pure single colors\n'
        '  text = text.replace(/\\b([WUBRGCX])\\b(?![\\/<])/g, (m, sym) => {\n'
        '    return `<img src="${SCRYFALL}${sym.toUpperCase()}.svg">`;\n'
        '  });\n'
        '  return text;\n'
        '}\n'
        '\n'
        'function showModal(localIdx) {\n'
        '  const c = visibleCards[localIdx];\n'
        '  if (!c) return;\n'
        '  const rules = renderRulesSymbols((c.rules||"").replace(/\\n/g,"<br>"));\n'
        '  document.getElementById("modal-body").innerHTML =\n'
        '    (c.image ? `<img src="cards/${c.image}" onerror="this.style.display=\'none\';">` : "") +\n'
        '    `<div class="modal-name">${c.name}</div>` +\n'
        '    `<div class="modal-cost">${formatCost(c.mana_symbols)}</div>` +\n'
        '    `<div class="modal-type">${c.type||""}</div>` +\n'
        '    `<div class="modal-rules">${rules}</div>` +\n'
        '    (c.flavor ? `<div class="modal-flavor">${c.flavor}</div>` : "") +\n'
        '    (c.pt ? `<div class="modal-pt">${c.pt}</div>` : "") +\n'
        '    `<div class="modal-meta">` +\n'
        '      (c.rarity ? `<span class="badge">${c.rarity}</span>` : "") +\n'
        '      (c.color_label ? `<span class="badge">${c.color_label}</span>` : "") +\n'
        '      (c.cmc!==undefined ? `<span class="badge">CMC ${c.cmc}</span>` : "") +\n'
        '    `</div>`;\n'
        '  document.getElementById("modal").classList.add("active");\n'
        '}\n'
        '\n'
        'function closeModal() { document.getElementById("modal").classList.remove("active"); }\n'
        'function modalBgClick(e) { if (e.target===document.getElementById("modal")) closeModal(); }\n'
        '\n'
        'const CD = {\n'
        '  plugins: { legend: { labels: { color:"#7a7060", font:{size:10} } } },\n'
        '  scales: {\n'
        '    x: { ticks:{color:"#7a7060",font:{size:9}}, grid:{color:"#ffffff0a"} },\n'
        '    y: { ticks:{color:"#7a7060",font:{size:9}}, grid:{color:"#ffffff0a"} }\n'
        '  }\n'
        '};\n'
        '\n'
        'function updateCharts(active) {\n'
        '  const colorMap={}, cmcC={}, typeC={Creature:0,Instant:0,Sorcery:0,Enchantment:0,Artifact:0,Land:0,Other:0};\n'
        '  active.forEach(c => {\n'
        '    colorMap[c.color_label] = (colorMap[c.color_label]||0)+1;\n'
        '    cmcC[c.cmc] = (cmcC[c.cmc]||0)+1;\n'
        '    let found=false;\n'
        '    ["Creature","Sorcery","Instant","Artifact","Enchantment","Land"].forEach(t => { if((c.type||"").includes(t)){typeC[t]++;found=true;} });\n'
        '    if(!found) typeC.Other++;\n'
        '  });\n'
        '  const lkeys=["White","Blue","Black","Red","Green","Azorius","Orzhov","Boros","Selesnya","Dimir","Izzet","Simic","Rakdos","Golgari","Gruul","Colorless","Land"];\n'
        '  const cl=lkeys.filter(k=>colorMap[k]>0);\n'
        '  chart1.data.labels=cl; chart1.data.datasets[0].data=cl.map(k=>colorMap[k]||0); chart1.update();\n'
        '  const mx=Math.max(...Object.keys(cmcC).map(Number),5);\n'
        '  const cl2=Array.from({length:mx+1},(_,i)=>i);\n'
        '  chart2.data.labels=cl2.map(k=>k>=9?"9+":k); chart2.data.datasets[0].data=cl2.map(l=>cmcC[l]||0); chart2.update();\n'
        '  chart3.data.datasets[0].data=Object.values(typeC); chart3.update();\n'
        '}\n'
        '\n'
        'function initCharts() {\n'
        '  const lkeys=["White","Blue","Black","Red","Green","Azorius","Orzhov","Boros","Selesnya","Dimir","Izzet","Simic","Rakdos","Golgari","Gruul","Colorless","Land"];\n'
        '  const colorMap={}, cmcC={}, typeC={Creature:0,Sorcery:0,Instant:0,Artifact:0,Enchantment:0,Land:0,Other:0};\n'
        '  ALL_CARDS.filter(c=>!c.is_token).forEach(c=>{\n'
        '    colorMap[c.color_label]=(colorMap[c.color_label]||0)+1;\n'
        '    cmcC[c.cmc]=(cmcC[c.cmc]||0)+1;\n'
        '    let found=false;\n'
        '    ["Creature","Sorcery","Instant","Artifact","Enchantment","Land"].forEach(t=>{if((c.type||"").includes(t)){typeC[t]++;found=true;}});\n'
        '    if(!found) typeC.Other++;\n'
        '  });\n'
        '\n'
        '  const cl=lkeys.filter(k=>colorMap[k]>0);\n'
        '  chart1=new Chart(document.getElementById("colorChart"),{\n'
        '    type:"bar",\n'
        '    data:{labels:cl,datasets:[{data:cl.map(k=>colorMap[k]||0),backgroundColor:"#c89b3c88",borderColor:"#c89b3c",borderWidth:1}]},\n'
        '    options:{...CD,plugins:{legend:{display:false}},responsive:true,maintainAspectRatio:false,\n'
        '      onClick:(e,els)=>{ if(els.length){document.getElementById("color-filter").value=chart1.data.labels[els[0].index];applyFilters();} }}\n'
        '  });\n'
        '\n'
        '  const mx=Math.max(...Object.keys(cmcC).map(Number),5);\n'
        '  const cl2=Array.from({length:mx+1},(_,i)=>i);\n'
        '  chart2=new Chart(document.getElementById("cmcChart"),{\n'
        '    type:"bar",\n'
        '    data:{labels:cl2.map(k=>k>=9?"9+":k),datasets:[{data:cl2.map(l=>cmcC[l]||0),backgroundColor:"#c89b3c88",borderColor:"#c89b3c",borderWidth:1}]},\n'
        '    options:{...CD,plugins:{legend:{display:false}},responsive:true,maintainAspectRatio:false,\n'
        '      onClick:(e,els)=>{ if(els.length){let v=chart2.data.labels[els[0].index].toString().replace("+","");document.getElementById("cmc-filter").value=v;applyFilters();} }}\n'
        '  });\n'
        '\n'
        '  chart3=new Chart(document.getElementById("typeChart"),{\n'
        '    type:"doughnut",\n'
        '    data:{labels:Object.keys(typeC),datasets:[{data:Object.values(typeC),backgroundColor:["#4a9e6b","#6aadff","#aa88ff","#ffaa44","#ff6688","#c89b3c","#7a7060"],borderColor:"#1a1e30",borderWidth:2}]},\n'
        '    options:{responsive:true,maintainAspectRatio:false,\n'
        '      plugins:{legend:{position:"right",labels:{color:"#7a7060",font:{size:9},boxWidth:12}}},\n'
        '      onClick:(e,els)=>{ if(els.length){const lb=chart3.data.labels[els[0].index];if(document.querySelector(`#type-filter option[value="${lb}"]`)){document.getElementById("type-filter").value=lb;applyFilters();}} }}\n'
        '  });\n'
        '\n'
        '  applyFilters();\n'
        '}\n'
        '\n'
        'window.onload = initCharts;\n'
        '</script>\n'
        '</body>\n'
        '</html>\n'
    )
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Parsing MSE file...")
    cards = parse_mse(MSE_FILE)
    print(f"Found {len(cards)} cards")

    print("Computing analytics...")
    analytics = compute_analytics(cards)

    print("Building gallery...")
    html = build_html(cards, analytics)
    with open(os.path.join(REPO_DIR, "docs", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    print("Saving card data...")
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    print("Pushing to GitHub...")
    os.chdir(REPO_DIR)
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", f"Update set — {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    subprocess.run(["git", "push"])
    print("Done! Visit: https://hlobbdaboss.github.io/dota2-UB/")


if __name__ == "__main__":
    main()
EOF