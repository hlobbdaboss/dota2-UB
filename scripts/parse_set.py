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

def clean_mse_text(text):
    """Remove MSE markup tags like <word-list-type-en>"""
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def parse_mse(filepath):
    with zipfile.ZipFile(filepath, 'r') as z:
        # Extract all card images
        print("Extracting card images...")
        os.makedirs(IMAGES_DIR, exist_ok=True)
        for name in z.namelist():
            if name.endswith('.png'):
                with z.open(name) as img_file:
                    img_data = img_file.read()
                    out_path = os.path.join(IMAGES_DIR, name)
                    with open(out_path, 'wb') as f:
                        f.write(img_data)

        # Read set data
        with z.open('set') as f:
            content = f.read().decode('utf-8')

    cards = []
    # Split into card blocks
    blocks = content.split('\ncard:\n')
    
    for block in blocks[1:]:  # Skip header
        card = {}
        lines = block.splitlines()
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.startswith('name:'):
                card['name'] = stripped[5:].strip()
            elif stripped.startswith('casting_cost:'):
                card['cost'] = stripped[13:].strip()
            elif stripped.startswith('image:'):
                card['image'] = stripped[6:].strip()
            elif stripped.startswith('super_type:'):
                card['super_type'] = clean_mse_text(stripped[11:].strip())
            elif stripped.startswith('sub_type:'):
                card['sub_type'] = clean_mse_text(stripped[9:].strip())
            elif stripped.startswith('rarity:'):
                card['rarity'] = stripped[7:].strip()
            elif stripped.startswith('rule_text:'):
                card['rules'] = clean_mse_text(stripped[10:].strip())
            elif stripped.startswith('flavor_text:'):
                card['flavor'] = clean_mse_text(stripped[12:].strip())
            elif stripped.startswith('pt:'):
                card['pt'] = stripped[3:].strip()

        if 'name' in card and card['name']:
            # Build full type line
            super_type = card.get('super_type', '')
            sub_type = card.get('sub_type', '')
            if sub_type:
                card['type'] = f"{super_type} — {sub_type}"
            else:
                card['type'] = super_type
            cards.append(card)

    return cards

def get_rarity_color(rarity):
    colors = {
        'common': '#aaa',
        'uncommon': '#6af',
        'rare': '#fa6',
        'mythic rare': '#f6a',
        'basic land': '#aaa'
    }
    return colors.get(rarity.lower(), '#aaa')

def build_html(cards):
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dota 2 Cube — Universes Beyond</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #1a1a2e; color: #eee; font-family: Georgia, serif; padding: 20px; }
        h1 { text-align: center; color: #c89b3c; font-size: 2.5em; margin-bottom: 5px; padding-top: 20px; }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; }
        .controls { display: flex; justify-content: center; gap: 10px; margin-bottom: 25px; flex-wrap: wrap; }
        input, select { padding: 8px 12px; background: #2a2a4e; border: 1px solid #c89b3c; 
                        color: #eee; border-radius: 5px; font-size: 0.9em; }
        .grid { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; }
        .card { width: 180px; cursor: pointer; transition: transform 0.2s; }
        .card:hover { transform: scale(1.05); }
        .card img { width: 100%; border-radius: 8px; display: block; }
        .card-name { text-align: center; font-size: 0.75em; color: #c89b3c; 
                     margin-top: 4px; font-weight: bold; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                 background: rgba(0,0,0,0.85); z-index: 100; justify-content: center; align-items: center; }
        .modal.active { display: flex; }
        .modal-content { background: #2a2a4e; border: 1px solid #c89b3c; border-radius: 12px;
                         padding: 25px; max-width: 500px; width: 90%; position: relative; }
        .modal img { width: 100%; border-radius: 8px; margin-bottom: 15px; }
        .modal h2 { color: #c89b3c; margin-bottom: 5px; }
        .modal .cost { color: #aaa; margin-bottom: 5px; }
        .modal .type { color: #888; font-style: italic; margin-bottom: 10px; }
        .modal .rules { line-height: 1.6; margin-bottom: 10px; }
        .modal .flavor { color: #999; font-style: italic; border-top: 1px solid #444; 
                         padding-top: 10px; line-height: 1.5; }
        .modal .pt { text-align: right; color: #c89b3c; font-weight: bold; margin-top: 8px; }
        .close { position: absolute; top: 10px; right: 15px; cursor: pointer; 
                 color: #aaa; font-size: 1.5em; }
        .close:hover { color: #fff; }
    </style>
</head>
<body>
    <h1>Dota 2 Cube</h1>
    <p class="subtitle">Universes Beyond — """ + str(len(cards)) + """ cards</p>
    <div class="controls">
        <input type="text" id="search" placeholder="Search cards..." onkeyup="filterCards()">
        <select id="rarity" onchange="filterCards()">
            <option value="">All Rarities</option>
            <option value="common">Common</option>
            <option value="uncommon">Uncommon</option>
            <option value="rare">Rare</option>
            <option value="mythic rare">Mythic</option>
        </select>
    </div>
    <div class="grid" id="grid">
"""

    for card in cards:
        image = card.get('image', '')
        rarity = card.get('rarity', '').lower()
        name = card.get('name', '')
        
        html += f"""        <div class="card" 
            data-name="{name.lower()}" 
            data-rarity="{rarity}"
            onclick="showModal({json.dumps(card)})">
            {"<img src='cards/" + image + "' alt='" + name + "' onerror=\"this.style.display='none'\">" if image else ""}
            <div class="card-name">{name}</div>
        </div>
"""

    html += """    </div>

    <div class="modal" id="modal" onclick="closeModal(event)">
        <div class="modal-content">
            <span class="close" onclick="document.getElementById('modal').classList.remove('active')">✕</span>
            <div id="modal-body"></div>
        </div>
    </div>

    <script>
        function filterCards() {
            const query = document.getElementById('search').value.toLowerCase();
            const rarity = document.getElementById('rarity').value.toLowerCase();
            document.querySelectorAll('.card').forEach(card => {
                const nameMatch = card.dataset.name.includes(query);
                const rarityMatch = !rarity || card.dataset.rarity === rarity;
                card.style.display = (nameMatch && rarityMatch) ? 'block' : 'none';
            });
        }

        function showModal(card) {
            const body = document.getElementById('modal-body');
            body.innerHTML = `
                ${card.image ? `<img src="cards/${card.image}" alt="${card.name}">` : ''}
                <h2>${card.name}</h2>
                <div class="cost">${card.cost || ''}</div>
                <div class="type">${card.type || ''}</div>
                <div class="rules">${(card.rules || '').replace(/\\n/g, '<br>')}</div>
                ${card.flavor ? `<div class="flavor">${card.flavor}</div>` : ''}
                ${card.pt ? `<div class="pt">${card.pt}</div>` : ''}
            `;
            document.getElementById('modal').classList.add('active');
        }

        function closeModal(event) {
            if (event.target === document.getElementById('modal')) {
                document.getElementById('modal').classList.remove('active');
            }
        }
    </script>
</body>
</html>"""
    return html

def main():
    print("Parsing MSE file...")
    cards = parse_mse(MSE_FILE)
    print(f"Found {len(cards)} cards")

    print("Building gallery...")
    html = build_html(cards)
    with open(os.path.join(REPO_DIR, "docs", "index.html"), "w") as f:
        f.write(html)

    print("Saving card data...")
    with open(OUTPUT_JSON, "w") as f:
        json.dump(cards, f, indent=2)

    print("Pushing to GitHub...")
    os.chdir(REPO_DIR)
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", f"Update set — {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    subprocess.run(["git", "push"])
    print("Done! Site will update in ~1 minute.")
    print(f"Visit: https://hlobbdaboss.github.io/dota2-UB/")

if __name__ == "__main__":
    main()