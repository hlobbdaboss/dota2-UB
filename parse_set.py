import os
import zipfile
import re
import json

# Paths
MSE_FILE_PATH = "/Users/Harrison_1/Desktop/Full-Magic-Pack-main/Sets/Dota Set.mse-set"
EXTRACT_DIR = "./temp_mse"
DOCS_DIR = "./docs"

def clean_tags(text):
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()

def parse_mse_set():
    if not os.path.exists(MSE_FILE_PATH):
        print(f"Error: Could not find MSE file at {MSE_FILE_PATH}")
        return

    print("Extracting MSE set file...")
    with zipfile.ZipFile(MSE_FILE_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    set_data_path = os.path.join(EXTRACT_DIR, "set")
    if not os.path.exists(set_data_path):
        print("Error: 'set' data file not found.")
        return

    print("Parsing analytics engine matrix...")
    card_list = []
    current_card = None
    in_text_block = False
    text_lines = []

    with open(set_data_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.strip() == "card:":
                if current_card and current_card.get('name'):
                    if text_lines:
                        current_card['text'] = "\n".join(text_lines)
                    card_list.append(current_card)
                current_card = {'name': '', 'super_type': '', 'sub_type': '', 'mana': '', 'text': '', 'power': '', 'toughness': '', 'rarity': 'common'}
                text_lines = []
                in_text_block = False
                continue

            if current_card is None:
                continue

            if in_text_block:
                if line.startswith("\t\t") or line.startswith("  "):
                    text_lines.append(clean_tags(line))
                    continue
                else:
                    in_text_block = False
                    if text_lines:
                        current_card['text'] = "\n".join(text_lines)
                        text_lines = []

            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue

            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key == "name":
                current_card['name'] = clean_tags(value)
            elif key == "casting_cost":
                current_card['mana'] = clean_tags(value)
            elif key == "super_type":
                current_card['super_type'] = clean_tags(value)
            elif key == "sub_type":
                current_card['sub_type'] = clean_tags(value)
            elif key == "power":
                current_card['power'] = clean_tags(value)
            elif key == "toughness":
                current_card['toughness'] = clean_tags(value)
            elif key == "rarity":
                current_card['rarity'] = clean_tags(value).lower()
            elif key == "rule_text":
                in_text_block = True
                if value:
                    text_lines.append(clean_tags(value))

        if current_card and current_card.get('name'):
            if text_lines:
                current_card['text'] = "\n".join(text_lines)
            card_list.append(current_card)

    # Clean types, calculate CMC, and assign exact Guild color combos
    for card in card_list:
        if card['super_type'] and card['sub_type']:
            card['type'] = f"{card['super_type']} — {card['sub_type']}"
        else:
            card['type'] = card['super_type'] if card['super_type'] else "Unknown"
        
        card['is_legendary'] = "Legendary" in card['type']
        
        # Calculate precise CMC
        digits = re.findall(r'\d+', card['mana'])
        num_mana = int(digits[0]) if digits else 0
        symbols_count = len(re.sub(r'\d+', '', card['mana']))
        card['cmc'] = num_mana + symbols_count

        # Build strict alphabetical color string (e.g., 'WU', 'BR')
        found_colors = []
        for sym in ['W', 'U', 'B', 'R', 'G']:
            if sym in card['mana']:
                found_colors.append(sym)
        
        card['colors'] = found_colors
        
        if not found_colors:
            if "Land" in card['type']:
                card['color_group'] = 'Land'
            else:
                card['color_group'] = 'Colorless'
        elif len(found_colors) > 1:
            card['color_group'] = "".join(found_colors) # Dynamic guild label like 'WU'
        else:
            card['color_group'] = found_colors[0]

    # Default sort the master card list array by CMC (low to high)
    card_list.sort(key=lambda c: c['cmc'])

    generate_html(card_list)

    import shutil
    shutil.rmtree(EXTRACT_DIR)
    print(f"Successfully compiled advanced studio workspace for {len(card_list)} cards!")

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
        h1 { margin-top: 0; font-size: 2.2em; border-bottom: 2px solid #222; padding-bottom: 10px; color: #fff; }
        
        .dashboard-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .chart-card { background: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 8px; padding: 15px; height: 280px; display: flex; flex-direction: column; align-items: center; }
        .chart-card h3 { margin: 0 0 10px 0; font-size: 1em; color: #aaa; text-align: left; width: 100%; }
        .chart-container { position: relative; width: 100%; height: 100%; }

        /* Filter controls layout grid */
        .controls { background: #1a1a1a; padding: 20px; border-radius: 8px; border: 1px solid #2a2a2a; margin-bottom: 25px; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; align-items: center; }
        .control-group { display: flex; flex-direction: column; gap: 5px; }
        .control-group label { font-size: 0.85em; color: #888; font-weight: bold; text-transform: uppercase; }
        .search-box, .select-box { background: #2b2b2b; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 6px; font-size: 0.95em; width: 100%; box-sizing: border-box; }
        
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .card { background: #1e1e1e; border-left: 5px solid #444; border-top: 1px solid #2a2a2a; border-right: 1px solid #2a2a2a; border-bottom: 1px solid #2a2a2a; border-radius: 6px; padding: 15px; display: flex; flex-direction: column; justify-content: space-between; min-height: 160px; }
        
        /* Color themes framework */
        .card.monocolor-W { border-left-color: #f0f2c5; }
        .card.monocolor-U { border-left-color: #0077ff; }
        .card.monocolor-B { border-left-color: #242424; }
        .card.monocolor-R { border-left-color: #ff3333; }
        .card.monocolor-G { border-left-color: #00aa44; }
        .card.color-Multicolor { border-left-color: #d4af37; }
        .card.color-Colorless { border-left-color: #7a7a7a; }
        .card.color-Land { border-left-color: #8b5a2b; }

        .card-header { margin-bottom: 5px; display: flex; justify-content: space-between; align-items: flex-start; }
        .card-name { font-size: 1.15em; font-weight: bold; color: #fff; max-width: 75%; }
        .card-mana { color: #ffca28; font-weight: bold; }
        .card-type { font-style: italic; font-size: 0.85em; color: #888; margin-bottom: 10px; border-bottom: 1px solid #2a2a2a; padding-bottom: 4px; }
        .card-text { font-size: 0.9em; white-space: pre-wrap; line-height: 1.4; color: #bbb; flex-grow: 1; margin-bottom: 10px; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; font-size: 0.85em; color: #777; }
        .rarity-tag { text-transform: uppercase; font-size: 0.8em; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        .rarity-common { background: #333; color: #bbb; }
        .rarity-uncommon { background: #4b6584; color: #fff; }
        .rarity-rare { background: #b8860b; color: #fff; }
        .rarity-mythic { background: #8b0000; color: #ffca28; }
        .card-pt { font-weight: bold; color: #fff; font-size: 1.05em; }
    </style>
</head>
<body>

    <h1>Dota 2 Cube — Studio Dashboard</h1>

    <div class="dashboard-row">
        <div class="chart-card">
            <h3>Color / Guild Balance</h3>
            <div class="chart-container"><canvas id="colorChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Mana Curve (CMC)</h3>
            <div class="chart-container"><canvas id="manaChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Card Types Breakdown</h3>
            <div class="chart-container"><canvas id="typeChart"></canvas></div>
        </div>
    </div>

    <!-- Multi-tier analytics matrix selectors -->
    <div class="controls">
        <div class="control-group">
            <label>Search Text</label>
            <input type="text" id="search" class="search-box" placeholder="Name or rule details...">
        </div>
        <div class="control-group">
            <label>Color Profile</label>
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
            <label>Rarity / Frame</label>
            <select id="legendFilter" class="select-box" onchange="applyFilters()">
                <option value="All">All Cards</option>
                <option value="Legendary">Legendary Only</option>
                <option value="Non-Legendary">Non-Legendary</option>
            </select>
        </div>
    </div>

    <div class="card-grid" id="grid"></div>

    <script>
        const cardsData = __CARDS_JSON_PLACEHOLDER__;

        function renderGrid(filteredCards) {
            const grid = document.getElementById('grid');
            grid.innerHTML = '';
            
            filteredCards.forEach(card => {
                const ptDisplay = (card.power || card.toughness) ? `<div class="card-pt">${card.power}/${card.toughness}</div>` : '<div></div>';
                
                // Color highlight class assigning logic
                let borderClass = `color-${card.color_group}`;
                if (card.colors.length === 1) {
                    borderClass = `monocolor-${card.colors[0]}`;
                } else if (card.colors.length > 1) {
                    borderClass = 'color-Multicolor';
                }

                const cardEl = document.createElement('div');
                cardEl.className = `card ${borderClass}`;
                
                cardEl.innerHTML = `
                    <div>
                        <div class="card-header">
                            <div class="card-name">${card.name}</div>
                            <span class="card-mana">${card.mana ? card.mana : '0'}</span>
                        </div>
                        <div class="card-type">${card.type}</div>
                        <div class="card-text">${card.text}</div>
                    </div>
                    <div class="card-footer">
                        <span class="rarity-tag rarity-${card.rarity}">CMC ${card.cmc} — ${card.rarity}</span>
                        ${ptDisplay}
                    </div>
                `;
                grid.appendChild(cardEl);
            });
        }

        function applyFilters() {
            const searchText = document.getElementById('search').value.toLowerCase();
            const colorSel = document.getElementById('colorFilter').value;
            const cmcSel = document.getElementById('cmcFilter').value;
            const typeSel = document.getElementById('typeFilter').value;
            const legendSel = document.getElementById('legendFilter').value;

            const filtered = cardsData.filter(card => {
                const matchesSearch = card.name.toLowerCase().includes(searchText) || card.text.toLowerCase().includes(searchText);
                
                let matchesColor = true;
                if (colorSel !== 'All') {
                    if (colorSel === 'Multicolor') {
                        matchesColor = card.colors.length > 1;
                    } else if (colorSel === 'W' || colorSel === 'U' || colorSel === 'B' || colorSel === 'R' || colorSel === 'G') {
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

                const matchesType = (typeSel === 'All') || card.type.includes(typeSel);
                
                let matchesLegend = true;
                if (legendSel === 'Legendary') matchesLegend = card.is_legendary;
                if (legendSel === 'Non-Legendary') matchesLegend = !card.is_legendary;

                return matchesSearch && matchesColor && matchesCmc && matchesType && matchesLegend;
            });
            renderGrid(filtered);
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

            // Map standard groupings for dynamic chart keys
            const labelKeys = ['W', 'U', 'B', 'R', 'G', 'WU', 'WB', 'WR', 'WG', 'UB', 'UR', 'UG', 'BR', 'BG', 'RG', 'Colorless', 'Land'];
            const displayLabels = ['W', 'U', 'B', 'R', 'G', 'Azorius', 'Orzhov', 'Boros', 'Selesnya', 'Dimir', 'Izzet', 'Simic', 'Rakdos', 'Golgari', 'Gruul', 'Colorless', 'Land'];
            const chartColors = ['#f0f2c5', '#0077ff', '#242424', '#ff3333', '#00aa44', '#70a1ff', '#747d8c', '#ff6b81', '#2ed573', '#57606f', '#ff7f50', '#1e90ff', '#ff4757', '#a4b0be', '#ffa502', '#7a7a7a', '#8b5a2b'];
            
            const dynamicData = labelKeys.map(k => colorMap[k] || 0);

            new Chart(document.getElementById('colorChart'), {
                type: 'bar',
                data: {
                    labels: displayLabels,
                    datasets: [{
                        data: dynamicData,
                        backgroundColor: chartColors
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });

            const maxCmc = Math.max(...Object.keys(cmcCounts).map(Number), 0);
            const cmcLabels = Array.from({length: maxCmc + 1}, (_, i) => i);
            const cmcData = cmcLabels.map(l => cmcCounts[l] || 0);

            new Chart(document.getElementById('manaChart'), {
                type: 'bar',
                data: {
                    labels: cmcLabels,
                    datasets: [{ data: cmcData, backgroundColor: '#ffca28' }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });

            new Chart(document.getElementById('typeChart'), {
                type: 'doughnut',
                data: {
                    labels: Object.keys(typeCounts),
                    datasets: [{ data: Object.values(typeCounts), backgroundColor: ['#2ecc71','#3498db','#9b59b6','#e67e22','#f1c40f','#e74c3c','#95a5a6'] }]
                },
                options: { responsive: true, maintainAspectRatio: false }
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
