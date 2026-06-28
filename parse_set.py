import os
import zipfile
import re
import json

MSE_FILE_PATH = "/Users/Harrison_1/Desktop/Full-Magic-Pack-main/Sets/Dota Set.mse-set"
EXTRACT_DIR = "./temp_mse"
DOCS_DIR = "./docs"

def clean_tags(text):
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()

def parse_hybrid_and_cmc(mana_string):
    if not mana_string:
        return 0, []
    
    raw_symbols = mana_string.strip().replace(" ", "")
    generic_match = re.match(r'^(\d+)', raw_symbols)
    generic_amt = int(generic_match.group(1)) if generic_match else 0
    symbol_part = re.sub(r'^\d+', '', raw_symbols)
    
    if "/" in symbol_part:
        parts = [p for p in symbol_part.split("/") if p]
        symbol_count = len(parts)
        flat_symbols = "".join(parts)
    else:
        symbol_count = len(symbol_part)
        flat_symbols = symbol_part
        
    cmc = generic_amt + symbol_count
    
    colors = []
    for c in ['W', 'U', 'B', 'R', 'G']:
        if c in flat_symbols:
            colors.append(c)
            
    return cmc, colors

def parse_mse_set():
    if not os.path.exists(MSE_FILE_PATH):
        print(f"Error: Could not find MSE file at {MSE_FILE_PATH}")
        return

    print("Extracting archive engine...")
    with zipfile.ZipFile(MSE_FILE_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    set_data_path = os.path.join(EXTRACT_DIR, "set")
    if not os.path.exists(set_data_path):
        print("Error: 'set' data file not found.")
        return

    print("Parsing hybrid schema assets...")
    card_list = []
    current_card = None
    in_text_block = False
    text_target = "text"
    text_store = {"text": [], "text_2": []}

    with open(set_data_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.strip() == "card:":
                if current_card and current_card.get('name'):
                    current_card['text'] = "\n".join(text_store["text"]).strip()
                    current_card['text_2'] = "\n".join(text_store["text_2"]).strip()
                    card_list.append(current_card)
                current_card = {
                    'name': '', 'super_type': '', 'sub_type': '', 'mana': '', 'text': '', 'power': '', 'toughness': '', 'rarity': 'common',
                    'name_2': '', 'super_type_2': '', 'sub_type_2': '', 'text_2': '', 'power_2': '', 'toughness_2': ''
                }
                text_store = {"text": [], "text_2": []}
                in_text_block = False
                continue

            if current_card is None:
                continue

            if in_text_block:
                if line.startswith("\t\t") or line.startswith("  "):
                    text_store[text_target].append(clean_tags(line))
                    continue
                else:
                    in_text_block = False

            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue

            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key == "name": current_card['name'] = clean_tags(value)
            elif key == "casting_cost": current_card['mana'] = clean_tags(value)
            elif key == "super_type": current_card['super_type'] = clean_tags(value)
            elif key == "sub_type": current_card['sub_type'] = clean_tags(value)
            elif key == "power": current_card['power'] = clean_tags(value)
            elif key == "toughness": current_card['toughness'] = clean_tags(value)
            elif key == "rarity": current_card['rarity'] = clean_tags(value).lower()
            elif key == "rule_text":
                in_text_block = True
                text_target = "text"
                if value: text_store["text"].append(clean_tags(value))
            elif key == "name_2": current_card['name_2'] = clean_tags(value)
            elif key == "super_type_2": current_card['super_type_2'] = clean_tags(value)
            elif key == "sub_type_2": current_card['sub_type_2'] = clean_tags(value)
            elif key == "power_2": current_card['power_2'] = clean_tags(value)
            elif key == "toughness_2": current_card['toughness_2'] = clean_tags(value)
            elif key == "rule_text_2":
                in_text_block = True
                text_target = "text_2"
                if value: text_store["text_2"].append(clean_tags(value))

        if current_card and current_card.get('name'):
            current_card['text'] = "\n".join(text_store["text"]).strip()
            current_card['text_2'] = "\n".join(text_store["text_2"]).strip()
            card_list.append(current_card)

    for card in card_list:
        card['type'] = f"{card['super_type']} — {card['sub_type']}" if card['super_type'] and card['sub_type'] else (card['super_type'] if card['super_type'] else "Unknown")
        card['is_dfc'] = bool(card['name_2'].strip())
        if card['is_dfc']:
            card['type_2'] = f"{card['super_type_2']} — {card['sub_type_2']}" if card['super_type_2'] and card['sub_type_2'] else (card['super_type_2'] if card['super_type_2'] else "")
        card['is_legendary'] = "Legendary" in card['type'] or "Legendary" in card.get('type_2', '')
        card['cmc'], card['colors'] = parse_hybrid_and_cmc(card['mana'])

        if not card['colors']:
            card['color_group'] = 'Land' if "Land" in card['type'] else 'Colorless'
        elif len(card['colors']) > 1:
            card['color_group'] = "".join(card['colors'])
        else:
            card['color_group'] = card['colors'][0]

    generate_html(card_list)

    import shutil
    shutil.rmtree(EXTRACT_DIR)
    print(f"Successfully fixed loop parser schemas for {len(card_list)} cards!")

def generate_html(cards):
    os.makedirs(DOCS_DIR, exist_ok=True)
    html_path = os.path.join(DOCS_DIR, "index.html")
    cards_json = json.dumps(cards)

    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dota 2 Cube Studio Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #121212; color: #e0e0e0; padding: 25px; margin: 0; }
        .header-row { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #222; padding-bottom: 10px; margin-bottom: 20px; }
        h1 { margin: 0; font-size: 2.2em; color: #fff; }
        
        .dashboard-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .chart-card { background: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 8px; padding: 15px; height: 280px; display: flex; flex-direction: column; align-items: center; cursor: pointer; }
        .chart-card h3 { margin: 0 0 10px 0; font-size: 1em; color: #aaa; text-align: left; width: 100%; }
        .chart-container { position: relative; width: 100%; height: 100%; }

        .kpi-card { background: #1e1e1e; border: 1px solid #ffca28; border-radius: 8px; padding: 15px; height: 280px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-sizing: border-box; }
        .kpi-number { font-size: 4.5em; font-weight: 800; color: #ffca28; line-height: 1; margin-bottom: 10px; }
        .kpi-label { font-size: 0.9em; text-transform: uppercase; letter-spacing: 1.5px; color: #888; font-weight: bold; text-align: center; }

        .controls { background: #1a1a1a; padding: 20px; border-radius: 8px; border: 1px solid #2a2a2a; margin-bottom: 25px; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; align-items: center; }
        .control-group { display: flex; flex-direction: column; gap: 5px; }
        .control-group label { font-size: 0.85em; color: #888; font-weight: bold; text-transform: uppercase; }
        .search-box, .select-box { background: #2b2b2b; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 6px; font-size: 0.95em; width: 100%; box-sizing: border-box; }
        .reset-btn { background: #ff4757; border: none; color: white; padding: 11px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 0.95em; width: 100%; transition: background 0.2s; margin-top: 18px; }
        .reset-btn:hover { background: #ff6b81; }
        
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 20px; align-items: start; }
        .card-container-3d { perspective: 1000px; min-height: 200px; }
        .card-inner-3d { position: relative; width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; }
        .card-container-3d.flipped .card-inner-3d { transform: rotateY(180deg); }
        
        .card { background: #1e1e1e; border-left: 5px solid #444; border-top: 1px solid #2a2a2a; border-right: 1px solid #2a2a2a; border-bottom: 1px solid #2a2a2a; border-radius: 6px; padding: 15px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; }
        
        .dfc-front, .dfc-back { backface-visibility: hidden; width: 100%; -webkit-backface-visibility: hidden; }
        .dfc-back { position: absolute; top: 0; left: 0; transform: rotateY(180deg); height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 15px; background: #1e1e1e; border-left: 5px dashed #ffca28; border-top: 1px solid #2a2a2a; border-right: 1px solid #2a2a2a; border-bottom: 1px solid #2a2a2a; border-radius: 6px; box-sizing: border-box; }

        .card.color-Multicolor { border-left-color: #d4af37; }
        .card.color-Colorless { border-left-color: #7a7a7a; }
        .card.color-Land { border-left-color: #8b5a2b; }
        .card.monocolor-W { border-left-color: #f0f2c5; }
        .card.monocolor-U { border-left-color: #0077ff; }
        .card.monocolor-B { border-left-color: #444444; }
        .card.monocolor-R { border-left-color: #ff3333; }
        .card.monocolor-G { border-left-color: #00aa44; }

        .card-header { margin-bottom: 5px; display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
        .card-name { font-size: 1.15em; font-weight: bold; color: #fff; max-width: 65%; }
        
        .card-mana { text-align: right; display: flex; gap: 3px; justify-content: flex-end; flex-wrap: wrap; max-width: 35%; padding-top: 2px; }
        .svg-symbol { width: 18px; height: 18px; border-radius: 50%; box-shadow: 0 1px 2px rgba(0,0,0,0.6); vertical-align: middle; display: inline-block; }
        .card-text .svg-symbol { width: 15px; height: 15px; margin: 0 1px; vertical-align: -2px; }

        .card-type { font-style: italic; font-size: 0.85em; color: #888; margin-bottom: 10px; border-bottom: 1px solid #2a2a2a; padding-bottom: 4px; }
        .card-text { font-size: 0.9em; white-space: pre-wrap; line-height: 1.4; color: #bbb; flex-grow: 1; margin-bottom: 10px; }
        .flip-btn { background: #333; border: 1px solid #555; color: #ffca28; font-size: 0.75em; padding: 3px 8px; border-radius: 4px; cursor: pointer; font-weight: bold; display: flex; align-items: center; gap: 4px; }
        .flip-btn:hover { background: #444; }

        .card-footer { display: flex; justify-content: space-between; align-items: center; font-size: 0.85em; color: #777; margin-top: auto; width: 100%; box-sizing: border-box; }
        .rarity-tag { text-transform: uppercase; font-size: 0.8em; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        .rarity-common { background: #333; color: #bbb; }
        .rarity-uncommon { background: #4b6584; color: #fff; }
        .rarity-rare { background: #b8860b; color: #fff; }
        .rarity-mythic { background: #8b0000; color: #ffca28; }
        .card-pt { font-weight: bold; color: #fff; font-size: 1.05em; }
    </style>
</head>
<body>

    <div class="header-row">
        <h1>Dota 2 Cube — Creative Suite</h1>
    </div>

    <div class="dashboard-row">
        <div class="kpi-card">
            <div class="kpi-number" id="kpiCounter">0</div>
            <div class="kpi-label" id="kpiLabel">Cards Selected</div>
        </div>
        <div class="chart-card" style="grid-column: span 2;">
            <h3>Color / Guild Balance (Click bars to filter)</h3>
            <div class="chart-container"><canvas id="colorChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Mana Curve</h3>
            <div class="chart-container"><canvas id="manaChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Card Types</h3>
            <div class="chart-container"><canvas id="typeChart"></canvas></div>
        </div>
    </div>

    <div class="controls">
        <div class="control-group">
            <label>Search Content</label>
            <input type="text" id="search" class="search-box" placeholder="Name or text details...">
        </div>
        <div class="control-group">
            <label>Color Identity</label>
            <select id="colorFilter" class="select-box" onchange="applyFilters()">
                <option value="All">All Identities</option>
                <option value="W">White</option>
                <option value="U">Blue</option>
                <option value="B">Black</option>
                <option value="R">Red</option>
                <option value="G">Green</option>
                <option value="Multicolor">Any Multicolor</option>
                <option value="WU">Azorius (WU)</option>
                <option value="WB">Orzhov (WB)</option>
                <option value="WR">Boros (WR)</option>
                <option value="WG">Selesnya (WG)</option>
                <option value="UB">Dimir (UB)</option>
                <option value="UR">Izzet (UR)</option>
                <option value="UG">Simic (UG)</option>
                <option value="BR">Rakdos (BR)</option>
                <option value="BG">Golgari (BG)</option>
                <option value="RG">Gruul (RG)</option>
                <option value="Colorless">Colorless</option>
                <option value="Land">Lands</option>
            </select>
        </div>
        <div class="control-group">
            <label>Mana Value (CMC)</label>
            <select id="cmcFilter" class="select-box" onchange="applyFilters()">
                <option value="All">All Costs</option>
                <option value="0">0 CMC</option>
                <option value="1">1 CMC</option>
                <option value="2">2 CMC</option>
                <option value="3">3 CMC</option>
                <option value="4">4 CMC</option>
                <option value="5">5 CMC</option>
                <option value="6">6 CMC</option>
                <option value="7">7+ CMC</option>
            </select>
        </div>
        <div class="control-group">
            <label>Card Type</label>
            <select id="typeFilter" class="select-box" onchange="applyFilters()">
                <option value="All">All Types</option>
                <option value="Creature">Creature</option>
                <option value="Instant">Instant</option>
                <option value="Sorcery">Sorcery</option>
                <option value="Artifact">Artifact</option>
                <option value="Enchantment">Enchantment</option>
                <option value="Planeswalker">Planeswalker</option>
                <option value="Land">Land</option>
            </select>
        </div>
        <div class="control-group">
            <label>Frame Variant</label>
            <select id="legendFilter" class="select-box" onchange="applyFilters()">
                <option value="All">All Frames</option>
                <option value="Legendary">Legendary Only</option>
                <option value="DFC">Double-Faced (DFC)</option>
            </select>
        </div>
        <div class="control-group">
            <label>Sort Order</label>
            <select id="sortFilter" class="select-box" onchange="applyFilters()">
                <option value="cmc">Mana Value (Low-High)</option>
                <option value="alpha">Alphabetical (A-Z)</option>
                <option value="power">Power (High-Low)</option>
            </select>
        </div>
        <div class="control-group">
            <button class="reset-btn" onclick="resetAllFilters()">Reset Filters</button>
        </div>
    </div>

    <div class="card-grid" id="grid"></div>

    <script>
        let cardsData = __CARDS_JSON_PLACEHOLDER__;
        let chart1, chart2, chart3;

        function formatManaSymbols(manaStr) {
            if (!manaStr) return '';
            let s = manaStr.trim ? manaStr.trim() : manaStr;
            s = s.replace(/\\s+/g, '').toUpperCase();
            
            let outputHtml = '';
            let genericMatch = s.match(/^(\\d+)/);
            if (genericMatch) {
                outputHtml += `<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/${genericMatch[1]}.svg" />`;
                s = s.replace(/^\\d+/, '');
            }
            
            if (s.includes('/')) {
                let cleanHybrid = s.replace(/\\//g, '');
                outputHtml += `<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/${cleanHybrid}.svg" />`;
            } else {
                for (let i = 0; i < s.length; i++) {
                    let char = s[i];
                    if (['W','U','B','R','G','C','X'].includes(char)) {
                        outputHtml += `<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/${char}.svg" />`;
                    }
                }
            }
            return outputHtml;
        }

        // Dedicated granular split engine parses hybrid activations with perfect isolation
        function formatRulesText(textStr) {
            if (!textStr) return '';
            let formatted = textStr;
            
            // Format tap activation notation tags explicitly
            formatted = formatted.replace(/\\bT\\s*,/gi, '<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/T.svg" /> ,');
            formatted = formatted.replace(/\\bT:/gi, '<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/T.svg" />:');
            
            // Target isolated single-character hybrid components (e.g., R/W) step by step
            // without condensing sequences like R/W R/W R/W into a single word blocks
            formatted = formatted.replace(/([WUBRGCX])\\/([WUBRGCX])/gi, (match, p1, p2) => {
                const combined = (p1 + p2).toUpperCase();
                return `<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/${combined}.svg" />`;
            });

            // Parse remaining baseline monocolor letters
            const monoTokens = ['W', 'U', 'B', 'R', 'G', 'C'];
            monoTokens.forEach(token => {
                let regex = new RegExp('\\\\b' + token + '\\\\b', 'g');
                formatted = formatted.replace(regex, `<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/${token}.svg" />`);
            });

            // Map standard text block integers
            formatted = formatted.replace(/\\b(\\d+)\\b/g, (m, p1) => {
                if (formatted.indexOf('/') === formatted.indexOf(m) + 1) return p1;
                return `<img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/${p1}.svg" />`;
            });
            return formatted;
        }

        function toggleFlip(btn) {
            const container = btn.closest('.card-container-3d');
            container.classList.toggle('flipped');
        }

        function renderGrid(filteredCards) {
            const grid = document.getElementById('grid');
            grid.innerHTML = '';
            
            document.getElementById('kpiCounter').innerText = filteredCards.length;
            
            filteredCards.forEach(card => {
                let ptDisplay = (card.power || card.toughness) ? `<div class="card-pt">${card.power}/${card.toughness}</div>` : '<div></div>';
                
                let borderClass = `color-${card.color_group}`;
                if (card.colors.length === 1) {
                    borderClass = `monocolor-${card.colors[0]}`;
                } else if (card.colors.length > 1) {
                    borderClass = 'color-Multicolor';
                }

                let backFaceHtml = '';
                if (card.is_dfc) {
                    const backPt = (card.power_2 || card.toughness_2) ? `<div class="card-pt">${card.power_2}/${card.toughness_2}</div>` : '<div></div>';
                    backFaceHtml = `
                        <div class="dfc-back">
                            <div>
                                <div class="card-header">
                                    <div class="card-name">${card.name_2}</div>
                                    <span class="card-mana"><img class="svg-symbol" src="https://svgs.scryfall.io/card-symbols/CARD.svg" /></span>
                                </div>
                                <div class="card-type">${card.type_2}</div>
                                <div class="card-text">${formatRulesText(card.text_2)}</div>
                            </div>
                            <div class="card-footer" style="margin-top: 12px;">
                                <button class="flip-btn" onclick="toggleFlip(this)">Transform 🔄</button>
                                ${backPt}
                            </div>
                        </div>
                    `;
                }

                if (!card.is_dfc) {
                    const cardEl = document.createElement('div');
                    cardEl.className = `card ${borderClass}`;
                    cardEl.innerHTML = `
                        <div>
                            <div class="card-header">
                                <div class="card-name">${card.name}</div>
                                <span class="card-mana">${formatManaSymbols(card.mana)}</span>
                            </div>
                            <div class="card-type">${card.type}</div>
                            <div class="card-text">${formatRulesText(card.text)}</div>
                        </div>
                        <div class="card-footer" style="margin-top: 12px;">
                            <span class="rarity-tag rarity-${card.rarity}">CMC ${card.cmc} — ${card.rarity}</span>
                            ${ptDisplay}
                        </div>
                    `;
                    grid.appendChild(cardEl);
                } else {
                    const containerEl = document.createElement('div');
                    containerEl.className = 'card-container-3d';
                    
                    containerEl.innerHTML = `
                        <div class="card-inner-3d">
                            <div class="card dfc-front ${borderClass}">
                                <div>
                                    <div class="card-header">
                                        <div class="card-name">${card.name}</div>
                                        <span class="card-mana">${formatManaSymbols(card.mana)}</span>
                                    </div>
                                    <div class="card-type">${card.type}</div>
                                    <div class="card-text">${formatRulesText(card.text)}</div>
                                </div>
                                <div class="card-footer" style="margin-top: 12px;">
                                    <button class="flip-btn" onclick="toggleFlip(this)">Transform 🔄</button>
                                    ${ptDisplay}
                                </div>
                            </div>
                            ${backFaceHtml}
                        </div>
                    `;
                    grid.appendChild(containerEl);
                }
            });
        }

        function applyFilters() {
            const searchText = document.getElementById('search').value.toLowerCase();
            const colorSel = document.getElementById('colorFilter').value;
            const cmcSel = document.getElementById('cmcFilter').value;
            const typeSel = document.getElementById('typeFilter').value;
            const legendSel = document.getElementById('legendFilter').value;
            const sortSel = document.getElementById('sortFilter').value;

            let filtered = cardsData.filter(card => {
                const textHaystack = (card.name + " " + card.text + " " + card.name_2 + " " + card.text_2).toLowerCase();
                const matchesSearch = textHaystack.includes(searchText);
                
                let matchesColor = true;
                if (colorSel !== 'All') {
                    if (colorSel === 'Multicolor') {
                        matchesColor = card.colors.length > 1;
                    } else if (['W','U','B','R','G'].includes(colorSel)) {
                        matchesColor = card.colors.length === 1 && card.colors[0] === colorSel;
                    } else {
                        matchesColor = card.color_group === colorSel;
                    }
                }

                let matchesCmc = true;
                if (cmcSel !== 'All') {
                    if (cmcSel === '7') {
                        matchesCmc = card.cmc >= 7;
                    } else {
                        matchesCmc = card.cmc === parseInt(cmcSel);
                    }
                }

                const matchesType = (typeSel === 'All') || card.type.includes(typeSel) || (card.type_2 && card.type_2.includes(typeSel));
                
                let matchesLegend = true;
                if (legendSel === 'Legendary') matchesLegend = card.is_legendary;
                if (legendSel === 'DFC') matchesLegend = card.is_dfc;

                return matchesSearch && matchesColor && matchesCmc && matchesType && matchesLegend;
            });

            if (sortSel === 'alpha') {
                filtered.sort((a, b) => a.name.localeCompare(b.name));
            } else if (sortSel === 'power') {
                filtered.sort((a, b) => {
                    let pA = parseInt(a.power) || 0;
                    let pB = parseInt(b.power) || 0;
                    return pB - pA;
                });
            } else {
                filtered.sort((a, b) => a.cmc - b.cmc);
            }

            renderGrid(filtered);
        }

        function resetAllFilters() {
            document.getElementById('search').value = '';
            document.getElementById('colorFilter').value = 'All';
            document.getElementById('cmcFilter').value = 'All';
            document.getElementById('typeFilter').value = 'All';
            document.getElementById('legendFilter').value = 'All';
            document.getElementById('sortFilter').value = 'cmc';
            applyFilters();
        }

        document.getElementById('search').addEventListener('input', applyFilters);

        function buildCharts() {
            const colorMap = {};
            const cmcCounts = {};
            const typeCounts = { Creature:0, Sorcery:0, Instant:0, Artifact:0, Enchantment:0, Planeswalker:0, Other:0 };

            cardsData.forEach(c => {
                colorMap[c.color_group] = (colorMap[c.color_group] || 0) + 1;
                cmcCounts[c.cmc] = (cmcCounts[c.cmc] || 0) + 1;
                
                let foundType = false;
                ['Creature', 'Sorcery', 'Instant', 'Artifact', 'Enchantment', 'Planeswalker'].forEach(t => {
                    if (c.type.includes(t)) { typeCounts[t]++; foundType = true; }
                });
                if (!foundType) typeCounts.Other++;
            });

            const labelKeys = ['W', 'U', 'B', 'R', 'G', 'WU', 'WB', 'WR', 'WG', 'UB', 'UR', 'UG', 'BR', 'BG', 'RG', 'Colorless', 'Land'];
            const displayLabels = ['W', 'U', 'B', 'R', 'G', 'Azorius', 'Orzhov', 'Boros', 'Selesnya', 'Dimir', 'Izzet', 'Simic', 'Rakdos', 'Golgari', 'Gruul', 'Colorless', 'Land'];
            const chartColors = ['#f0f2c5', '#0077ff', '#242424', '#ff3333', '#00aa44', '#70a1ff', '#747d8c', '#ff6b81', '#2ed573', '#57606f', '#ff7f50', '#1e90ff', '#ff4757', '#a4b0be', '#ffa502', '#7a7a7a', '#8b5a2b'];
            const dynamicData = labelKeys.map(k => colorMap[k] || 0);

            const ctx1 = document.getElementById('colorChart');
            chart1 = new Chart(ctx1, {
                type: 'bar',
                data: {
                    labels: displayLabels,
                    datasets: [{ data: dynamicData, backgroundColor: chartColors, borderColor: '#555', borderWidth: 1.5 }]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    plugins: { legend: { display: false } },
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            document.getElementById('colorFilter').value = labelKeys[index];
                            applyFilters();
                        }
                    }
                }
            });

            const maxCmc = Math.max(...Object.keys(cmcCounts).map(Number), 0);
            const cmcLabels = Array.from({length: maxCmc + 1}, (_, i) => i);
            const cmcData = cmcLabels.map(l => cmcCounts[l] || 0);

            const ctx2 = document.getElementById('manaChart');
            chart2 = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: cmcLabels,
                    datasets: [{ data: cmcData, backgroundColor: '#ffca28', borderColor: '#444', borderWidth: 1 }]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    plugins: { legend: { display: false } },
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const selectedCmc = cmcLabels[index];
                            document.getElementById('cmcFilter').value = selectedCmc >= 7 ? '7' : selectedCmc.toString();
                            applyFilters();
                        }
                    }
                }
            });

            const ctx3 = document.getElementById('typeChart');
            const typeKeys = Object.keys(typeCounts);
            chart3 = new Chart(ctx3, {
                type: 'doughnut',
                data: {
                    labels: typeKeys,
                    datasets: [{ data: Object.values(typeCounts), backgroundColor: ['#2ecc71','#3498db','#9b59b6','#e67e22','#f1c40f','#e74c3c','#95a5a6'], borderColor: '#222', borderWidth: 1.5 }]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false,
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const typeClicked = typeKeys[index];
                            document.getElementById('typeFilter').value = typeClicked === 'Other' ? 'All' : typeClicked;
                            applyFilters();
                        }
                    }
                }
            });
        }

        renderGrid(cardsData);
        buildCharts();
    </script>
</body>
</html>
"""
    html_content = html_content.replace("__CARDS_JSON_PLACEHOLDER__", cards_json)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    parse_mse_set()
