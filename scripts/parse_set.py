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
    """
    Convert MSE casting_cost string into a list of pip tokens.
    MSE hybrid format: W/BW/B  →  [{W/B}, {W/B}]
    MSE phyrexian:     W/P     →  [{W/P}]
    Generic numerals and X are single tokens.
    """
    if not cost_str:
        return []

    tokens = []
    i = 0
    s = cost_str.strip()

    while i < len(s):
        # Try to match a hybrid/phyrexian pip: two chars, slash, two chars  e.g. W/B or G/W or 2/W
        # MSE concatenates hybrid pips with no separator, e.g. "W/BW/B"
        # We detect a hybrid pip as: (char)(char?)/( char)(char?)
        # Simple approach: look for '/' and grab the surrounding characters
        if i + 2 < len(s) and s[i+1] == '/':
            # single char / single char  e.g. W/B, G/W, R/G, B/R, X/Y
            pip = s[i:i+3]   # e.g. "W/B"
            tokens.append(pip)
            i += 3
        elif i + 3 < len(s) and s[i+2] == '/':
            # two char / single char  e.g. "2/W" — phyrexian generic
            pip = s[i:i+4]
            tokens.append(pip)
            i += 4
        elif s[i].isdigit():
            # Collect multi-digit generic mana
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
            i += 1  # skip unknown characters

    return tokens


def mana_pip_html(pip):
    """Return an HTML span for a single mana pip."""
    # Colour map for single pips
    COLORS = {
        'W': ('#f9faf4', '#a89f7a', 'W'),
        'U': ('#0e68ab', '#0a4d80', 'U'),
        'B': ('#150b00', '#4a3728', 'B'),
        'R': ('#d3202a', '#a01820', 'R'),
        'G': ('#00733e', '#005c32', 'G'),
        'C': ('#c0b9bc', '#8a8086', 'C'),  # colourless
        'X': ('#888', '#555', 'X'),
    }
    # Hybrid pip colours (background is a gradient split)
    HYBRID_GRAD = {
        'W/U': ('#f9faf4', '#0e68ab'),
        'W/B': ('#f9faf4', '#150b00'),
        'U/B': ('#0e68ab', '#150b00'),
        'U/R': ('#0e68ab', '#d3202a'),
        'B/R': ('#150b00', '#d3202a'),
        'B/G': ('#150b00', '#00733e'),
        'R/G': ('#d3202a', '#00733e'),
        'R/W': ('#d3202a', '#f9faf4'),
        'G/W': ('#00733e', '#f9faf4'),
        'G/U': ('#00733e', '#0e68ab'),
        'W/G': ('#f9faf4', '#00733e'),
    }

    pip = pip.upper()

    style_base = (
        "display:inline-flex;align-items:center;justify-content:center;"
        "width:18px;height:18px;border-radius:50%;font-size:10px;"
        "font-weight:bold;border:1px solid rgba(0,0,0,0.4);"
        "margin:0 1px;vertical-align:middle;flex-shrink:0;"
    )

    if '/' in pip:
        left, right = pip.split('/', 1)
        if pip in HYBRID_GRAD:
            c1, c2 = HYBRID_GRAD[pip]
        else:
            c1 = COLORS.get(left, ('#888', '#555', left))[0]
            c2 = COLORS.get(right, ('#888', '#555', right))[0]
        text_color = '#000' if pip in ('W/U', 'G/W', 'R/W', 'W/G', 'G/U') else '#fff'
        bg = f"linear-gradient(135deg, {c1} 50%, {c2} 50%)"
        label = f"{left}/{right}"
        return (
            f'<span class="mana-pip" style="{style_base}background:{bg};color:{text_color};" '
            f'title="{{{label}}}">{label}</span>'
        )
    elif pip.lstrip('0123456789') == '':
        # Generic mana numeral
        return (
            f'<span class="mana-pip" style="{style_base}background:#bbb;color:#222;" '
            f'title="{{{pip}}}">{pip}</span>'
        )
    elif pip == 'X':
        return (
            f'<span class="mana-pip" style="{style_base}background:#888;color:#fff;" '
            f'title="{{X}}">X</span>'
        )
    else:
        c = COLORS.get(pip, ('#888', '#555', pip))
        text_color = '#222' if pip == 'W' else '#fff'
        return (
            f'<span class="mana-pip" style="{style_base}background:{c[0]};color:{text_color};" '
            f'title="{{{pip}}}">{pip}</span>'
        )


def mana_cost_html(cost_str):
    """Render a full casting cost string as HTML pips."""
    pips = parse_mana_cost(cost_str)
    return ''.join(mana_pip_html(p) for p in pips)


def cmc_from_cost(cost_str):
    """Calculate converted mana cost (CMC) from MSE cost string."""
    pips = parse_mana_cost(cost_str)
    total = 0
    for pip in pips:
        if pip == 'X':
            continue
        elif '/' in pip:
            total += 1
        elif pip.isdigit() or pip.lstrip('0123456789') == '':
            total += int(pip)
        else:
            total += 1
    return total


# ─── MSE parsing ──────────────────────────────────────────────────────────────

def clean_mse_text(text):
    """Remove MSE markup and clean up text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\\n', '\n')
    return text.strip()


def get_color_identity(cost_str, rules_text=''):
    """Derive color identity from mana cost and rules text."""
    pips = parse_mana_cost(cost_str)
    colors = set()
    color_map = {'W': 'W', 'U': 'U', 'B': 'B', 'R': 'R', 'G': 'G'}

    for pip in pips:
        for ch in pip:
            if ch in color_map:
                colors.add(ch)

    # Also scan rules text for mana symbols like {W}, {U} etc.
    for ch in 'WUBRG':
        if f'{{{ch}}}' in rules_text:
            colors.add(ch)

    return sorted(colors, key=lambda c: 'WUBRG'.index(c))


def color_identity_label(colors):
    """Convert a sorted list of colors to a guild/shard label."""
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
            content = f.read().decode('utf-8')

    cards = []
    blocks = content.split('\ncard:\n')

    for block in blocks[1:]:
        card = {}
        lines = block.splitlines()

        # Multi-line field accumulation
        current_field = None
        current_value = []

        for line in lines:
            stripped = line.strip()

            # Detect field start
            if stripped.startswith('name:'):
                card['name'] = stripped[5:].strip()
                current_field = None
            elif stripped.startswith('casting_cost:'):
                card['cost'] = stripped[13:].strip()
                current_field = None
            elif stripped.startswith('image:') and 'image_2' not in stripped and 'image_3' not in stripped:
                val = stripped[6:].strip()
                if val:
                    card['image'] = val
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
            card['colors'] = get_color_identity(card.get('cost', ''), card.get('rules', ''))
            card['color_label'] = color_identity_label(card['colors'])
            cards.append(card)

    return cards


# ─── Analytics helpers ────────────────────────────────────────────────────────

def compute_analytics(cards):
    # Exclude tokens and basic lands for most stats
    playable = [c for c in cards if 'Token' not in c.get('type', '') and c.get('name')]

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

        # Color identity
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

        # CMC
        cmc = min(c.get('cmc', 0), 9)
        cmc_counts[cmc] = cmc_counts.get(cmc, 0) + 1

        # Type
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

        /* ── Header ── */
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

        /* ── Analytics dashboard ── */
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

        /* ── Filters ── */
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

        /* ── Card grid ── */
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

        /* ── Modal ── */
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
            gap: 2px;
            margin-bottom: 6px;
            flex-wrap: wrap;
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
        <div class="stat-number" id="displayed-count">{analytics['total']}</div>
        <div class="stat-label">Cards</div>
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
const ANALYTICS = {analytics_json};

// ── Mana pip renderer (JS mirror of Python) ───────────────────────────────────
const COLOR_BG = {{
    W:'#f9faf4', U:'#0e68ab', B:'#150b00', R:'#d3202a', G:'#00733e', C:'#c0b9bc'
}};
const HYBRID_GRAD = {{
    'W/U':['#f9faf4','#0e68ab'], 'W/B':['#f9faf4','#150b00'],
    'U/B':['#0e68ab','#150b00'], 'U/R':['#0e68ab','#d3202a'],
    'B/R':['#150b00','#d3202a'], 'B/G':['#150b00','#00733e'],
    'R/G':['#d3202a','#00733e'], 'R/W':['#d3202a','#f9faf4'],
    'G/W':['#00733e','#f9faf4'], 'G/U':['#00733e','#0e68ab'],
    'W/G':['#f9faf4','#00733e'],
}};

function parseCost(cost) {{
    if (!cost) return [];
    const tokens = [];
    let i = 0;
    const s = cost.toUpperCase();
    while (i < s.length) {{
        if (i+2 < s.length && s[i+1] === '/') {{
            tokens.push(s.slice(i, i+3)); i += 3;
        }} else if (i+3 < s.length && s[i+2] === '/') {{
            tokens.push(s.slice(i, i+4)); i += 4;
        }} else if (/\\d/.test(s[i])) {{
            let j = i;
            while (j < s.length && /\\d/.test(s[j])) j++;
            tokens.push(s.slice(i, j)); i = j;
        }} else {{
            tokens.push(s[i]); i++;
        }}
    }}
    return tokens;
}}

function pipHtml(pip) {{
    const base = `display:inline-flex;align-items:center;justify-content:center;
        width:20px;height:20px;border-radius:50%;font-size:10px;font-weight:bold;
        border:1px solid rgba(0,0,0,0.5);margin:0 1px;vertical-align:middle;flex-shrink:0;`;
    pip = pip.toUpperCase();
    if (pip.includes('/')) {{
        const [l, r] = pip.split('/');
        const grad = HYBRID_GRAD[pip] || [COLOR_BG[l]||'#888', COLOR_BG[r]||'#888'];
        const light = ['W/U','G/W','R/W','W/G','G/U'].includes(pip);
        return `<span style="${{base}}background:linear-gradient(135deg,${{grad[0]}} 50%,${{grad[1]}} 50%);
            color:${{light?'#222':'#fff'}}" title="${{ '{' + pip + '}' }}">${{l}}/${{r}}</span>`;
    }} else if (/^\\d+$/.test(pip)) {{
        return `<span style="${{base}}background:#bbb;color:#222" title="${{ '{' + pip + '}' }}">${{pip}}</span>`;
    }} else if (pip === 'X') {{
        return `<span style="${{base}}background:#888;color:#fff" title="{{X}}">X</span>`;
    }} else {{
        const bg = COLOR_BG[pip] || '#888';
        const tc = pip === 'W' ? '#222' : '#fff';
        return `<span style="${{base}}background:${{bg}};color:${{tc}}" title="${{ '{' + pip + '}' }}">${{pip}}</span>`;
    }}
}}

function costHtml(cost) {{
    return parseCost(cost).map(pipHtml).join('');
}}

// ── Rarity helpers ────────────────────────────────────────────────────────────
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

// ── Filtering & sorting ───────────────────────────────────────────────────────
let visibleCards = [...ALL_CARDS];

function applyFilters() {{
    const q = document.getElementById('search').value.toLowerCase();
    const col = document.getElementById('color-filter').value;
    const typ = document.getElementById('type-filter').value;
    const rar = document.getElementById('rarity-filter').value;
    const cmc = document.getElementById('cmc-filter').value;
    const srt = document.getElementById('sort-filter').value;

    let filtered = ALL_CARDS.filter(c => {{
        const nameMatch = !q || (c.name||'').toLowerCase().includes(q) || (c.rules||'').toLowerCase().includes(q);
        const colMatch = !col || c.color_label === col;
        const typMatch = !typ || (c.type||'').includes(typ);
        const rarMatch = !rar || (c.rarity||'').toLowerCase() === rar;
        const cmcMatch = !cmc || (cmc === '6' ? c.cmc >= 6 : c.cmc == parseInt(cmc));
        return nameMatch && colMatch && typMatch && rarMatch && cmcMatch;
    }});

    // Sort
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
    document.getElementById('result-count').textContent = `${{filtered.length}} of ${{ALL_CARDS.length}} cards`;
    document.getElementById('displayed-count').textContent = filtered.length;
}}

function resetFilters() {{
    document.getElementById('search').value = '';
    document.getElementById('color-filter').value = '';
    document.getElementById('type-filter').value = '';
    document.getElementById('rarity-filter').value = '';
    document.getElementById('cmc-filter').value = '';
    document.getElementById('sort-filter').value = 'name';
    applyFilters();
}}

// ── Grid rendering ────────────────────────────────────────────────────────────
function renderGrid(cards) {{
    const grid = document.getElementById('grid');
    grid.innerHTML = cards.map((c, i) => {{
        const img = c.image
            ? `<img src="cards/${{c.image}}" alt="${{c.name}}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'no-img\\'>🎴</div>'">`
            : `<div class="no-img">🎴</div>`;
        return `<div class="card" onclick="showModal(${{ALL_CARDS.indexOf(c)}})">
            ${{img}}
            <div class="card-footer">
                <span class="card-name">${{c.name}}</span>
                <span class="rarity-dot ${{rarityClass(c.rarity)}}"></span>
            </div>
        </div>`;
    }}).join('');
}}

// ── Modal ─────────────────────────────────────────────────────────────────────
function showModal(idx) {{
    const c = ALL_CARDS[idx];
    const body = document.getElementById('modal-body');
    body.innerHTML = `
        ${{c.image ? `<img src="cards/${{c.image}}" alt="${{c.name}}">` : ''}}
        <div class="modal-name">${{c.name}}</div>
        <div class="modal-cost">${{costHtml(c.cost)}}</div>
        <div class="modal-type">${{c.type||''}}</div>
        <div class="modal-rules">${{(c.rules||'').replace(/\\n/g,'<br>')}}</div>
        ${{c.flavor ? `<div class="modal-flavor">${{c.flavor}}</div>` : ''}}
        ${{c.pt ? `<div class="modal-pt">${{c.pt}}</div>` : ''}}
        <div class="modal-meta">
            ${{c.rarity ? `<span class="badge">${{c.rarity}}</span>` : ''}}
            ${{c.color_label ? `<span class="badge">${{c.color_label}}</span>` : ''}}
            ${{c.cmc !== undefined ? `<span class="badge">CMC ${{c.cmc}}</span>` : ''}}
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

// ── Charts ────────────────────────────────────────────────────────────────────
const CHART_DEFAULTS = {{
    plugins: {{ legend: {{ labels: {{ color: '#7a7060', font: {{ size: 10 }} }} }} }},
    scales: {{
        x: {{ ticks: {{ color: '#7a7060', font: {{ size: 9 }} }}, grid: {{ color: '#ffffff0a' }} }},
        y: {{ ticks: {{ color: '#7a7060', font: {{ size: 9 }} }}, grid: {{ color: '#ffffff0a' }} }}
    }}
}};

// Color chart
const colorData = ANALYTICS.color_counts;
const colorLabels = Object.keys(colorData).filter(k => colorData[k] > 0);
const colorVals = colorLabels.map(k => colorData[k]);
new Chart(document.getElementById('colorChart'), {{
    type: 'bar',
    data: {{
        labels: colorLabels,
        datasets: [{{ data: colorVals, backgroundColor: '#c89b3c88', borderColor: '#c89b3c', borderWidth: 1 }}]
    }},
    options: {{ ...CHART_DEFAULTS, plugins: {{ legend: {{ display: false }} }}, responsive: true, maintainAspectRatio: true }}
}});

// CMC chart
const cmcData = ANALYTICS.cmc_counts;
new Chart(document.getElementById('cmcChart'), {{
    type: 'bar',
    data: {{
        labels: Object.keys(cmcData).map(k => k == 9 ? '9+' : k),
        datasets: [{{ data: Object.values(cmcData), backgroundColor: '#c89b3c88', borderColor: '#c89b3c', borderWidth: 1 }}]
    }},
    options: {{ ...CHART_DEFAULTS, plugins: {{ legend: {{ display: false }} }}, responsive: true, maintainAspectRatio: true }}
}});

// Type donut
const typeData = ANALYTICS.type_counts;
new Chart(document.getElementById('typeChart'), {{
    type: 'doughnut',
    data: {{
        labels: Object.keys(typeData),
        datasets: [{{
            data: Object.values(typeData),
            backgroundColor: ['#4a9e6b','#6aadff','#aa88ff','#ffaa44','#ff6688','#c89b3c','#7a7060'],
            borderColor: '#1a1e30', borderWidth: 2
        }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: true, plugins: {{ legend: {{ position: 'right', labels: {{ color: '#7a7060', font: {{ size: 9 }}, boxWidth: 12 }} }} }} }}
}});

// ── Init ──────────────────────────────────────────────────────────────────────
applyFilters();
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