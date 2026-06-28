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

    print("Parsing card data for dashboard analytics...")
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

    # Clean types, calculate CMC, and assign Color Identity
    for card in card_list:
        if card['super_type'] and card['sub_type']:
            card['type'] = f"{card['super_type']} — {card['sub_type']}"
        else:
            card['type'] = card['super_type'] if card['super_type'] else "Unknown"
        
        # Calculate CMC
        digits = re.findall(r'\d+', card['mana'])
        num_mana = int(digits[0]) if digits else 0
        symbols_count = len(re.sub(r'\d+', '', card['mana']))
        card['cmc'] = num_mana + symbols_count

        colors = []
        for sym in ['W', 'U', 'B', 'R', 'G']:
            if sym in card['mana']:
                colors.append(sym)
        
        if not colors:
            if "Land" in card['type']:
                card['color_group'] = 'Land'
            else:
                card['color_group'] = 'Colorless'
        elif len(colors) > 1:
            card['color_group'] = 'Multicolor'
        else:
            card['color_group'] = colors[0]

    generate_html(card_list)

    import shutil
    shutil.rmtree(EXTRACT_DIR)
    print(f"Successfully compiled dashboard data for {len(card_list)} cards!")

def generate_html(cards):
    os.makedirs(DOCS_DIR, exist_ok=True)
    html_path = os.path.join(DOCS_DIR, "index.html")
    
    cards_json = json.dumps(cards)

    # Plain string block prevents syntax issues with JavaScript's curly braces
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dota 2 Cube Analytics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #121212; color: #e0e0e0; padding: 25px; margin: 0; }
        h1 { margin-top: 0; font-size: 2.2em; border-bottom: 2px solid #222; padding-bottom: 10px; color: #fff; }
        .dashboard-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .chart-card { background: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 8px; padding: 15px; height: 260px; display: flex; flex-direction: column; align-items: center; }
        .chart-card h3 { margin: 0 0 10px 0; font-size: 1em; color: #aaa; text-align: left; width: 100%; }
        .chart-container { position: relative; width: 100%; height: 100%; }
        .controls { background: #1a1a1a; padding: 15px; border-radius: 8px; border: 1px solid #2a2a2a; margin-bottom: 25px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center; }
        .search-box { background: #2b2b2b; border: 1px solid #444; color: #fff; padding: 8px 12px; border-radius: 6px; font-size: 1em; min-width: 250px; }
        .filter-btn { background: #2b2b2b; border: 1px solid #444; color: #ccc; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9em; }
        .filter-btn.active { background: #ffca28; color: #000; border-color: #ffca28; font-weight: bold; }
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .card { background: #1e1e1e; border-left: 5px solid #444; border-top: 1px solid #2a2a2a; border-right: 1px solid #2a2a2a; border-bottom: 1px solid #2a2a2a; border-radius: 6px; padding: 15px; display: flex; flex-direction: column; justify-content: space-between; min-height: 160px; transition: transform 0.2s; }
        .card:hover { transform: translateY(-2px); }
        .card.color-W { border-left-color: #f0f2c5; }
        .card.color-U { border-left-color: #0077ff; }
        .card.color-B { border-left-color: #242424; }
        .card.color-R { border-left-color: #ff3333; }
        .card.color-G { border-left-color: #00aa44; }
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

    <h1>Dota 2 Cube — Set Dashboard</h1>

    <div class="dashboard-row">
        <div class="chart-card">
            <h3>Color Balance</h3>
            <div class="chart-container"><canvas id="colorChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Mana Curve (CMC)</h3>
            <div class="chart-container"><canvas id="manaChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Card Types</h3>
            <div class="chart-container"><canvas id="typeChart"></canvas></div>
        </div>
    </div>

    <div class="controls">
        <input type="text" id="search" class="search-box" placeholder="Search cards by name or rules...">
        <button class="filter-btn active" onclick="filterColor('All', this)">All</button>
        <button class="filter-btn" onclick="filterColor('W', this)">White</button>
        <button class="filter-btn" onclick="filterColor('U', this)">Blue</button>
        <button class="filter-btn" onclick="filterColor('B', this)">Black</button>
        <button class="filter-btn" onclick="filterColor('R', this)">Red</button>
        <button class="filter-btn" onclick="filterColor('G', this)">Green</button>
        <button class="filter-btn" onclick="filterColor('Multicolor', this)">Multicolor</button>
        <button class="filter-btn" onclick="filterColor('Colorless', this)">Colorless</button>
    </div>

    <div class="card-grid" id="grid"></div>

    <script>
        const cardsData = __CARDS_JSON_PLACEHOLDER__;
        let activeColorFilter = 'All';

        function renderGrid(filteredCards) {
            const grid = document.getElementById('grid');
            grid.innerHTML = '';
            
            filteredCards.forEach(card => {
                const ptDisplay = (card.power || card.toughness) ? `<div class="card-pt">${card.power}/${card.toughness}</div>` : '<div></div>';
                const cardEl = document.createElement('div');
                cardEl.className = `card color-${card.color_group}`;
                
                cardEl.innerHTML = `
                    <div>
                        <div class="card-header">
                            <div class="card-name">${card.name}</div>
                            <span class="card-mana">${card.mana}</span>
                        </div>
                        <div class="card-type">${card.type}</div>
                        <div class="card-text">${card.text}</div>
                    </div>
                    <div class="card-footer">
                        <span class="rarity-tag rarity-${card.rarity}">${card.rarity}</span>
                        ${ptDisplay}
                    </div>
                `;
                grid.appendChild(cardEl);
            });
        }

        function applyFilters() {
            const query = document.getElementById('search').value.toLowerCase();
            const filtered = cardsData.filter(card => {
                const matchesSearch = card.name.toLowerCase().includes(query) || card.text.toLowerCase().includes(query);
                const matchesColor = (activeColorFilter === 'All') || (card.color_group === activeColorFilter);
                return matchesSearch && matchesColor;
            });
            renderGrid(filtered);
        }

        function filterColor(color, btn) {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeColorFilter = color;
            applyFilters();
        }

        document.getElementById('search').addEventListener('input', applyFilters);

        function buildCharts() {
            const counts = { W:0, U:0, B:0, R:0, G:0, Multicolor:0, Colorless:0, Land:0 };
            const cmcCounts = {};
            const typeCounts = { Creature:0, Sorcery:0, Instant:0, Artifact:0, Enchantment:0, Planeswalker:0, Other:0 };

            cardsData.forEach(c => {
                counts[c.color_group] = (counts[c.color_group] || 0) + 1;
                cmcCounts[c.cmc] = (cmcCounts[c.cmc] || 0) + 1;
                
                let foundType = false;
                ['Creature', 'Sorcery', 'Instant', 'Artifact', 'Enchantment', 'Planeswalker'].forEach(t => {
                    if (c.type.includes(t)) { typeCounts[t]++; foundType = true; }
                });
                if (!foundType) typeCounts.Other++;
            });

            new Chart(document.getElementById('colorChart'), {
                type: 'doughnut',
                data: {
                    labels: ['White', 'Blue', 'Black', 'Red', 'Green', 'Multicolor', 'Colorless', 'Land'],
                    datasets: [{
                        data: [counts.W, counts.U, counts.B, counts.R, counts.G, counts.Multicolor, counts.Colorless, counts.Land],
                        backgroundColor: ['#f0f2c5', '#0077ff', '#242424', '#ff3333', '#00aa44', '#d4af37', '#7a7a7a', '#8b5a2b']
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
                type: 'polarArea',
                data: {
                    labels: Object.keys(typeCounts),
                    datasets: [{ data: Object.values(typeCounts), backgroundColor: ['#2ecc71','#3498db','#9b59b6','#e67e22','#f1c40f','#e74c3c','#95a5a6'] }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        renderGrid(cardsData);
        buildCharts();
    </script>
</body>
</html>
"""
    # Safe injection via direct string replacement
    html_content = html_content.replace("__CARDS_JSON_PLACEHOLDER__", cards_json)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    parse_mse_set()
