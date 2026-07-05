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

# ─── Mana cost parsing ────────────────────────────────────────────────────────

def parse_mana_cost(cost_str):
    if not cost_str:
        return []

    tokens = []
    i = 0
    s = cost_str.strip().replace(" ", "").upper()

    while i < len(s):
        if i + 2 < len(s) and s[i+1] == '/':
            pip = s[i:i+3]
            tokens.append(pip)
            i += 3
        elif i + 3 < len(s) and s[i+2] == '/':
            pip = s[i:i+4]
            tokens.append(pip)
            i += 4
        elif s[i].isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            tokens.append(s[i:j])
            i = j
        elif s[i] == 'X':
            tokens.append('X')
            i += 1
        elif s[i].isalpha():
            tokens.append(s[i])
            i += 1
        else:
            i += 1

    return tokens


def cmc_from_cost(cost_str):
    pips = parse_mana_cost(cost_str)
    total = 0
    for pip in pips:
        if pip == 'X':
            continue
        elif '/' in pip:
            total += 1
        elif pip.isdigit():
            total += int(pip)
        else:
            total += 1
    return total


# ─── MSE parsing ──────────────────────────────────────────────────────────────

def clean_mse_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\\n', '\n')
    return text.strip()


def get_color_identity(cost_str, rules_text=''):
    pips = parse_mana_cost(cost_str)
    colors = set()
    color_map = {'W': 'W', 'U': 'U', 'B': 'B', 'R': 'R', 'G': 'G'}

    for pip in pips:
        for ch in pip:
            if ch in color_map:
                colors.add(ch)

    for ch in 'WUBRG':
        if f'{{{ch}}}' in rules_text:
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


def parse_mse(filepath):
    with zipfile.ZipFile(filepath, 'r') as z:
        print("Extracting card images...")
        os.makedirs(IMAGES_DIR, exist_ok=True)
        for name in z.namelist():
            if name.endswith('.png'):
                with z.open(name) as img_file:
                    img_data = img_file.read()
                    out_path = os.path.join(IMAGES_DIR, name)
                    with open(out_path, 'wb') as f:
                        f.write(img_data)

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
            stripped = line.strip()

            if stripped.startswith('name:'):
                card['name'] = stripped[5:].strip()
                current_field = None
            elif stripped.startswith('casting_cost:'):
                card['cost'] = stripped[13:].strip()
                current_field = None
            elif stripped.startswith('image:') and 'image_2' not in stripped and 'image_3' not in stripped:
                val = stripped[6:].strip()
                if val:
                    card['image'] = f"{val}.png"
                current_field = None
            elif stripped.startswith('super_type:'):
                card['super_type'] = clean_mse_text(stripped[11:].strip())
                current_field = None
            elif stripped.startswith('sub_type:'):
                card['sub_type'] = clean_mse_text(stripped[9:].strip())
                current_field = None
            elif stripped.startswith('rarity:'):
                card['rarity'] = stripped[7:].strip()
                current_field = None
            elif stripped.startswith('rule_text:'):
                current_field = 'rules'
                current_value = [clean_mse_text(stripped[10:].strip())]
            elif stripped.startswith('flavor_text:'):
                if current_field and current_value:
                    card[current_field] = '\n'.join(current_value).strip()
                current_field = 'flavor'
                current_value = [clean_mse_text(stripped[12:].strip())]
            elif stripped.startswith('pt:'):
                if current_field and current_value:
                    card[current_field] = '\n'.join(current_value).strip()
                card['pt'] = stripped[3:].strip()
                current_field = None
            elif current_field and stripped and not ':' in stripped[:20]:
                current_value.append(clean_mse_text(stripped))

        if current_field and current_value:
            card[current_field] = '\n'.join(current_value).strip()

        if 'name' in card and card['name']:
            super_type = card.get('super_type', '')
            sub_type = card.get('sub_type', '')
            card['type'] = f"{super_type} — {sub_type}" if sub_type else super_type
            card['cmc'] = cmc_from_cost(card.get('cost', ''))
            
            card['is_token'] = "TOKEN" in card['type'].upper()
            
            card['mana_symbols'] = []
            pips = parse_mana_cost(card.get('cost', ''))
            for pip in pips:
                if '/' in pip:
                    card['mana_symbols'].append("".join(sorted(list(pip.replace("/", "")))))
                else:
                    card['mana_symbols'].append(pip)

            card['colors'] = get_color_identity(card.get('cost', ''), card.get('rules', ''))
            card['color_label'] = color_identity_label(card['colors'])
            cards.append(card)

    return cards


# ─── Analytics helpers ────────────────────────────────────────────────────────

def compute_analytics(cards):
    playable = [c for c in cards if not c.get('is_token', False) and c.get('name')]

    color_counts = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0,
                    'Azorius': 0, 'Orzhov': 0, 'Boros': 0, 'Selesnya': 0,
                    'Dimir': 0, 'Izzet': 0, 'Simic': 0,
                    'Rakdos': 0, 'Golgari': 0, 'Gruul': 0,
                    'Colorless': 0, 'Multicolor': 0, 'Land': 0}

    cmc_counts = {i: 0 for i in range(10)}
    type_counts = {'Creature': 0, 'Instant': 0, 'Sorcery': 0,
                   'Enchantment': 0, 'Artifact': 0, 'Land': 0, 'Other': 0}

    for c in playable:
        t = c.get('type', '')
        label = c.get('color_label', 'Colorless')
        colors = c.get('colors', [])

        if 'Land' in t:
            color_counts['Land'] = color_counts.get('Land', 0) + 1
        elif len(colors) == 0:
            color_counts['Colorless'] += 1
        elif len(colors) == 1:
            color_counts[colors[0]] = color_counts.get(colors[0], 0) + 1
        elif len(colors) == 2:
            color_counts[label] = color_counts.get(label, 0) + 1
        else:
            color_counts['Multicolor'] = color_counts.get('Multicolor', 0) + 1

        cmc = min(c.get('cmc', 0), 9)
        cmc_counts[cmc] = cmc_counts.get(cmc, 0) + 1

        if 'Land' in t:
            type_counts['Land'] += 1
        elif 'Creature' in t:
            type_counts['Creature'] += 1
        elif 'Instant' in t:
            type_counts['Instant'] += 1
        elif 'Sorcery' in t:
            type_counts['Sorcery'] += 1
        elif 'Enchantment' in t:
            type_counts['Enchantment'] += 1
        elif 'Artifact' in t:
            type_counts['Artifact'] += 1
        else:
            type_counts['Other'] += 1

    return {
        'total': len(playable),
        'color_counts': color_counts,
        'cmc_counts': cmc_counts,
        'type_counts': type_counts
    }


# ─── HTML builder ─────────────────────────────────────────────────────────────

def build_html(cards, analytics):
    cards_json = json.dumps(cards)
    analytics_json = json.dumps(analytics)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dota 2 Cube — Universes Beyond</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            background: #0d0f1a;
            color: #e8e0d0;
            font-family: 'Georgia', serif;
            min-height: 100vh;
        }}

        .header {{
            background: linear-gradient(180deg, #1a1228 0%, #0d0f1a 100%);
            border-bottom: 1px solid #c89b3c44;
            padding: 28px 24px 20px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.8em;
            color: #c89b3c;
            letter-spacing: 0.04em;
            text-shadow: 0 0 40px #c89b3c66;
            margin-bottom: 4px;
        }}
        .header .tagline {{
            color: #7a7060;
            font-size: 0.95em;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        .dashboard {{
            display: grid;
            grid-template-columns: 140px 1fr 1fr 1fr;
            gap: 12px;
            padding: 16px 20px;
            background: #111420;
            border-bottom: 1px solid #c89b3c22;
        }}
        .stat-box {{
            background: #1a1e30;
            border: 1px solid #c89b3c33;
            border-radius: 8px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .stat-number {{
            font-size: 3em;
            font-weight: bold;
            color: #c89b3c;
            line-height: 1;
        }}
        .stat-label {{
            font-size: 0.7em;
            color: #7a7060;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-top: 6px;
        }}
        .chart-box {{
            background: #1a1e30;
            border: 1px solid #c89b3c33;
            border-radius: 8px;
            padding: 12px;
        }}
        .chart-title {{
            font-size: 0.72em;
            color: #7a7060;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 8px;
        }}
        .chart-box canvas {{ max-height: 120px; }}

        .filters {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            padding: 14px 20px;
            background: #0d0f1a;
            border-bottom: 1px solid #c89b3c22;
            align-items: center;
        }}
        .filters input, .filters select {{
            background: #1a1e30;
            border: 1px solid #c89b3c44;
            color: #e8e0d0;
            padding: 7px 12px;
            border-radius: 6px;
            font-size: 0.85em;
            font-family: Georgia, serif;
        }}
        .filters input {{ width: 220px; }}
        .filters select {{ cursor: pointer; }}
        .filters input:focus, .filters select:focus {{
            outline: none;
            border-color: #c89b3c;
        }}
        .reset-btn {{
            background: #c89b3c;
            color: #0d0f1a;
            border: none;
            padding: 7px 16px;
            border-radius: 6px;
            font-size: 0.85em;
            font-weight: bold;
            cursor: pointer;
            font-family: Georgia, serif;
            margin-left: auto;
        }}
        .reset-btn:hover {{ background: #e0b44e; }}
        .result-count {{
            font-size: 0.8em;
            color: #7a7060;
            white-space: nowrap;
        }}

        .grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            padding: 16px 20px;
            justify-content: flex-start;
        }}
        .card {{
            width: 160px;
            cursor: pointer;
            transition: transform 0.15s, box-shadow 0.15s;
            border-radius: 8px;
            overflow: hidden;
            background: #1a1e30;
            border: 1px solid #c89b3c22;
        }}
        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(200,155,60,0.25);
            border-color: #c89b3c88;
        }}
        .card img {{
            width: 100%;
            display: block;
            aspect-ratio: 5/7;
            object-fit: cover;
        }}
        .card .no-img {{
            width: 100%;
            aspect-ratio: 5/7;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #12151f;
            color: #3a3520;
            font-size: 2em;
        }}
        .card-footer {{
            padding: 6px 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 4px;
        }}
        .card-name {{
            font-size: 0.68em;
            color: #c89b3c;
            font-weight: bold;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            flex: 1;
        }}
        .rarity-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .r-common {{ background: #999; }}
        .r-uncommon {{ background: #6aadff; }}
        .r-rare {{ background: #ffaa44; }}
        .r-mythic {{ background: #ff66aa; }}

        .modal {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.88);
            z-index: 200;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .modal.active {{ display: flex; }}
        .modal-inner {{
            background: #1a1e30;
            border: 1px solid #c89b3c66;
            border-radius: 12px;
            max-width: 480px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            position: relative;
            padding: 20px;
        }}
        .modal-close {{
            position: absolute;
            top: 12px; right: 16px;
            font-size: 1.4em;
            cursor: pointer;
            color: #7a7060;
            background: none;
            border: none;
            line-height: 1;
        }}
        .modal-close:hover {{ color: #e8e0d0; }}
        .modal img {{
            width: 100%;
            border-radius: 8px;
            margin-bottom: 14px;
        }}
        .modal-name {{
            font-size: 1.3em;
            color: #c89b3c;
            margin-bottom: 4px;
        }}
        .modal-cost {{
            display: flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }}
        .svg-symbol {{
            width: 18px;
            height: 18px;
            border-radius: 50%;
            box-shadow: 0 1px 2px rgba(0,0,0,0.6);
            vertical-align: middle;
            display: inline-block;
        }}
        .modal-type {{
            font-size: 0.85em;
            color: #7a7060;
            font-style: italic;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #c89b3c22;
        }}
        .modal-rules {{
            font-size: 0.88em;
            line-height: 1.65;
            margin-bottom: 10px;
            white-space: pre-line;
        }}
        .modal-flavor {{
            font-size: 0.8em;
            color: #7a7060;
            font-style: italic;
            border-top: 1px solid #c89b3c22;
            padding-top: 10px;
            line-height: 1.5;
        }}
        .modal-pt {{
            text-align: right;
            font-size: 1.1em;
            font-weight: bold;
            color: #c89b3c;
            margin-top: 8px;
        }}
        .modal-meta {{
            display: flex;
            gap: 8px;
            margin-top: 10px;
            flex-wrap: wrap;
        }}
        .badge {{
            font-size: 0.7em;
            padding: 2px 8px;
            border-radius: 20px;
            background: #0d0f1a;
            border: 1px solid #c89b3c44;
            color: #c89b3c;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }}
    </style>
</head>
<body>

<div class="header">
    <h1>Dota 2 Cube</h1>
    <div class="tagline">Universes Beyond &nbsp;·&nbsp; Custom Design Portfolio</div>
</div>

<div class="dashboard">
    <div class="stat-box">
        <div class="stat-number" id="displayed-count">0</div>
        <div class="stat-label" id="kpiLabel">Draft Cards</div>
    </div>
    <div class="chart-box">
        <div class="chart-title">Color Identity Distribution</div>
        <canvas id="colorChart"></canvas>
    </div>
    <div class="chart-box">
        <div class="chart-title">Mana Curve</div>
        <canvas id="cmcChart"></canvas>
    </div>
    <div class="chart-box">
        <div class="chart-title">Card Types</div>
        <canvas id="typeChart"></canvas>
    </div>
</div>

<div class="filters">
    <input type="text" id="search" placeholder="Search name or text…" oninput="applyFilters()">
    <select id="color-filter" onchange="applyFilters()">
        <option value="">All Colors</option>
        <option value="White">White</option>
        <option value="Blue">Blue</option>
        <option value="Black">Black</option>
        <option value="Red">Red</option>
        <option value="Green">Green</option>
        <option value="Azorius">Azorius (WU)</option>
        <option value="Orzhov">Orzhov (WB)</option>
        <option value="Boros">Boros (WR)</option>
        <option value="Selesnya">Selesnya (WG)</option>
        <option value="Dimir">Dimir (UB)</option>
        <option value="Izzet">Izzet (UR)</option>
        <option value="Simic">Simic (UG)</option>
        <option value="Rakdos">Rakdos (BR)</option>
        <option value="Golgari">Golgari (BG)</option>
        <option value="Gruul">Gruul (RG)</option>
        <option value="Colorless">Colorless</option>
    </select>
    <select id="type-filter" onchange="applyFilters()">
        <option value="">All Types</option>
        <option value="Creature">Creature</option>
        <option value="Instant">Instant</option>
        <option value="Sorcery">Sorcery</option>
        <option value="Enchantment">Enchantment</option>
        <option value="Artifact">Artifact</option>
        <option value="Land">Land</option>
    </select>
    <select id="rarity-filter" onchange="applyFilters()">
        <option value="">All Rarities</option>
        <option value="common">Common</option>
        <option value="uncommon">Uncommon</option>
        <option value="rare">Rare</option>
        <option value="mythic rare">Mythic</option>
    </select>
    <select id="cmc-filter" onchange="applyFilters()">
        <option value="">All CMC</option>
        <option value="0">0</option>
        <option value="1">1</option>
        <option value="2">2</option>
        <option value="3">3</option>
        <option value="4">4</option>
        <option value="5">5</option>
        <option value="6">6+</option>
    </select>
    <select id="variant-filter" onchange="applyFilters()">
        <option value="All">All Cube Cards</option>
        <option value="Token">Tokens & Emblems Only</option>
    </select>
    <select id="sort-filter" onchange="applyFilters()">
        <option value="name">Name (A–Z)</option>
        <option value="cmc">Mana Value</option>
        <option value="color">Color</option>
        <option value="rarity">Rarity</option>
        <option value="type">Type</option>
    </select>
    <span class="result-count" id="result-count"></span>
    <button class="reset-btn" onclick="resetFilters()">Reset Filters</button>
</div>

<div class="grid" id="grid"></div>

<div class="modal" id="modal" onclick="modalBgClick(event)">
    <div class="modal-inner">
        <button class="modal-close" onclick="closeModal()">✕</button>
        <div id="modal-body"></div>
    </div>
</div>

<script>
const ALL_CARDS = {cards_json};
let chart1, chart2, chart3;

// Properly escape single literal curly braces by doubling them for the Python f-string scope
function formatManaSymbols(manaSymbolsArray) {{
    if (!manaSymbolsArray || manaSymbolsArray.length === 0) return '';
    return manaSymbolsArray.map(sym => 
        `<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/\${{sym}}.svg" />`
    ).join('');
}}

function rarityClass(r) {{
    if (!r) return 'r-common';
    const rl = r.toLowerCase();
    if (rl.includes('mythic')) return 'r-mythic';
    if (rl === 'rare') return 'r-rare';
    if (rl === 'uncommon') return 'r-uncommon';
    return 'r-common';
}}

function rarityOrder(r) {{
    if (!r) return 0;
    const rl = r.toLowerCase();
    if (rl.includes('mythic')) return 3;
    if (rl === 'rare') return 2;
    if (rl === 'uncommon') return 1;
    return 0;
}}

let visibleCards = [...ALL_CARDS];

function applyFilters() {{
    const q = document.getElementById('search').value.toLowerCase();
    const col = document.getElementById('color-filter').value;
    const typ = document.getElementById('type-filter').value;
    const rar = document.getElementById('rarity-filter').value;
    const cmc = document.getElementById('cmc-filter').value;
    const variant = document.getElementById('variant-filter').value;
    const srt = document.getElementById('sort-filter').value;

    let filtered = ALL_CARDS.filter(c => {{
        const nameMatch = !q || (c.name||'').toLowerCase().includes(q) || (c.rules||'').toLowerCase().includes(q);
        const colMatch = !col || c.color_label === col;
        const typMatch = !typ || (c.type||'').includes(typ);
        const rarMatch = !rar || (c.rarity||'').toLowerCase() === rar;
        const cmcMatch = !cmc || (cmc === '6' ? c.cmc >= 6 : c.cmc == parseInt(cmc));
        
        let tokenMatch = true;
        if (variant === 'All') tokenMatch = !c.is_token;
        if (variant === 'Token') tokenMatch = c.is_token;
        
        return nameMatch && colMatch && typMatch && rarMatch && cmcMatch && tokenMatch;
    }});

    filtered.sort((a, b) => {{
        if (srt === 'name') return (a.name||'').localeCompare(b.name||'');
        if (srt === 'cmc') return (a.cmc||0) - (b.cmc||0) || (a.name||'').localeCompare(b.name||'');
        if (srt === 'color') return (a.color_label||'').localeCompare(b.color_label||'') || (a.name||'').localeCompare(b.name||'');
        if (srt === 'rarity') return rarityOrder(b.rarity) - rarityOrder(a.rarity) || (a.name||'').localeCompare(b.name||'');
        if (srt === 'type') return (a.type||'').localeCompare(b.type||'') || (a.name||'').localeCompare(b.name||'');
        return 0;
    }});

    visibleCards = filtered;
    renderGrid(filtered);
    document.getElementById('result-count').textContent = `\${{filtered.length}} of \${{ALL_CARDS.length}} cards`;
    document.getElementById('displayed-count').textContent = filtered.length;
    document.getElementById('kpiLabel').textContent = variant === 'Token' ? 'Tokens' : 'Draft Cards';
    
    updateCharts(filtered);
}}

function resetFilters() {{
    document.getElementById('search').value = '';
    document.getElementById('color-filter').value = '';
    document.getElementById('type-filter').value = '';
    document.getElementById('rarity-filter').value = '';
    document.getElementById('cmc-filter').value = '';
    document.getElementById('variant-filter').value = 'All';
    document.getElementById('sort-filter').value = 'name';
    applyFilters();
}}

function renderGrid(cards) {{
    const grid = document.getElementById('grid');
    grid.innerHTML = cards.map((c, i) => {{
        const img = c.image
            ? `<img src="cards/\${{c.image}}" alt="\${{c.name}}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'no-img\\'>🎴</div>'">`
            : `<div class="no-img">🎴</div>`;
        return `<div class="card" onclick="showModal(\${{ALL_CARDS.indexOf(c)}})">
            \${{img}}
            <div class="card-footer">
                <span class="card-name">\${{c.name}}</span>
                <span class="rarity-dot \${{rarityClass(c.rarity)}}"></span>
            </div>
        </div>`;
    }}).join('');
}}

function showModal(idx) {{
    const c = ALL_CARDS[idx];
    const body = document.getElementById('modal-body');
    body.innerHTML = `
        \${{c.image ? `<img src="cards/\${{c.image}}" alt="\${{c.name}}">` : ''}}
        <div class="modal-name">\${{c.name}}</div>
        <div class="modal-cost">\${{formatManaSymbols(c.mana_symbols)}}</div>
        <div class="modal-type">\${{c.type||''}}</div>
        <div class="modal-rules">\${{(c.rules||'').replace(/\\n/g,'<br>')}}</div>
        \${{c.flavor ? `<div class="modal-flavor">\${{c.flavor}}</div>` : ''}}
        \${{c.pt ? `<div class="modal-pt">\${{c.pt}}</div>` : ''}}
        <div class="modal-meta">
            \${{c.rarity ? `<span class="badge">\${{c.rarity}}</span>` : ''}}
            \${{c.color_label ? `<span class="badge">\${{c.color_label}}</span>` : ''}}
            \${{c.cmc !== undefined ? `<span class="badge">CMC \${{c.cmc}}</span>` : ''}}
        </div>
    `;
    document.getElementById('modal').classList.add('active');
}}

function closeModal() {{
    document.getElementById('modal').classList.remove('active');
}}

function modalBgClick(e) {{
    if (e.target === document.getElementById('modal')) closeModal();
}}

const CHART_DEFAULTS = {{
    plugins: {{ legend: {{ labels: {{ color: '#7a7060', font: {{ size: 10 }} }} }} }},
    scales: {{
        x: {{ ticks: {{ color: '#7a7060', font: {{ size: 9 }} }}, grid: {{ color: '#ffffff0a' }} }},
        y: {{ ticks: {{ color: '#7a7060', font: {{ size: 9 }} }}, grid: {{ color: '#ffffff0a' }} }}
    }}
}};

function updateCharts(activeCards) {{
    const colorMap = {{}};
    const cmcCounts = {{}};
    const typeCounts = {{ Creature:0, Instant:0, Sorcery:0, Enchantment:0, Artifact:0, Land:0, Other:0 }};

    activeCards.forEach(c => {{
        colorMap[c.color_label] = (colorMap[c.color_label] || 0) + 1;
        cmcCounts[c.cmc] = (cmcCounts[c.cmc] || 0) + 1;
        
        let found = false;
        ['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Land'].forEach(t => {{
            if ((c.type||'').includes(t)) {{ typeCounts[t]++; found = true; }}
        }});
        if (!found) typeCounts.Other++;
    }});

    const labelKeys = ['White', 'Blue', 'Black', 'Red', 'Green', 'Azorius', 'Orzhov', 'Boros', 'Selesnya', 'Dimir', 'Izzet', 'Simic', 'Rakdos', 'Golgari', 'Gruul', 'Colorless', 'Land'];
    chart1.data.labels = labelKeys.filter(k => colorMap[k] > 0);
    chart1.data.datasets[0].data = chart1.data.labels.map(k => colorMap[k] || 0);
    chart1.update();

    const maxCmc = Math.max(...Object.keys(cmcCounts).map(Number), 5);
    const cmcLabels = Array.from({{length: maxCmc + 1}}, (_, i) => i);
    chart2.data.labels = cmcLabels.map(k => k >= 6 ? '6+' : k);
    chart2.data.datasets[0].data = cmcLabels.map(l => cmcCounts[l] || 0);
    chart2.update();

    chart3.data.datasets[0].data = Object.values(typeCounts);
    chart3.update();
}}

function initCharts() {{
    const coreCards = ALL_CARDS.filter(c => !c.is_token);
    const colorMap = {{}};
    const cmcCounts = {{}};
    const typeCounts = {{ Creature:0, Instant:0, Sorcery:0, Enchantment:0, Artifact:0, Land:0, Other:0 }};

    coreCards.forEach(c => {{
        colorMap[c.color_label] = (colorMap[c.color_label] || 0) + 1;
        cmcCounts[c.cmc] = (cmcCounts[c.cmc] || 0) + 1;
        let found = false;
        ['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Land'].forEach(t => {{
            if ((c.type||'').includes(t)) {{ typeCounts[t]++; found = true; }}
        }});
        if (!found) typeCounts.Other++;
    }});

    const labelKeys = ['White', 'Blue', 'Black', 'Red', 'Green', 'Azorius', 'Orzhov', 'Boros', 'Selesnya', 'Dimir', 'Izzet', 'Simic', 'Rakdos', 'Golgari', 'Gruul', 'Colorless', 'Land'];

    chart1 = new Chart(document.getElementById('colorChart'), {{
        type: 'bar',
        data: {{ labels: labelKeys.filter(k => colorMap[k] > 0), datasets: [{{ data: labelKeys.filter(k => colorMap[k] > 0).map(k => colorMap[k] || 0), backgroundColor: '#c89b3c88', borderColor: '#c89b3c', borderWidth: 1 }}] }},
        options: {{ ...CHART_DEFAULTS, plugins: {{ legend: {{ display: false }} }}, responsive: true, maintainAspectRatio: false }}
    }});

    const maxCmc = Math.max(...Object.keys(cmcCounts).map(Number), 5);
    const cmcLabels = Array.from({{length: maxCmc + 1}}, (_, i) => i);
    chart2 = new Chart(document.getElementById('cmcChart'), {{
        type: 'bar',
        data: {{ labels: cmcLabels.map(k => k >= 6 ? '6+' : k), datasets: [{{ data: cmcLabels.map(l => cmcCounts[l] || 0), backgroundColor: '#c89b3c88', borderColor: '#c89b3c', borderWidth: 1 }}] }},
        options: {{ ...CHART_DEFAULTS, plugins: {{ legend: {{ display: false }} }}, responsive: true, maintainAspectRatio: false }}
    }});

    chart3 = new Chart(document.getElementById('typeChart'), {{
        type: 'doughnut',
        data: {{ labels: Object.keys(typeCounts), datasets: [{{ data: Object.values(typeCounts), backgroundColor: ['#4a9e6b','#6aadff','#aa88ff','#ffaa44','#ff6688','#c89b3c','#7a7a7a'], borderColor: '#1a1e30', borderWidth: 2 }}] }},
        options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'right', labels: {{ color: '#7a7060', font: {{ size: 9 }}, boxWidth: 12 }} }} }} }}
    }});

    applyFilters();
}}

window.onload = initCharts;
</script>
</body>
</html>"""
    return html


# ── Main ───────────────────────────────────────────────────────────────────────

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