import os
import zipfile
import re

MSE_FILE_PATH = "/Users/Harrison_1/Desktop/Full-Magic-Pack-main/Sets/Dota Set.mse-set"
EXTRACT_DIR = "./temp_mse"
DOCS_DIR = "./docs"

def clean_tags(text):
    if not text:
        return ""
    # Strip out MSE styling XML tags like <kw-a>, <word-list-type-en>, etc.
    clean = re.sub(r'<[^>]+>', '', text)
    # Clean up empty optional tags or fragments left behind
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

    print("Parsing modern card schema...")
    card_list = []
    current_card = None
    in_text_block = False
    text_lines = []

    with open(set_data_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # A new card block is indicated whenever we hit a line that is EXACTLY '\tcard:'
            # or a line that starts with 'card:' globally
            if line.strip() == "card:":
                if current_card and current_card.get('name'):
                    if text_lines:
                        current_card['text'] = "\n".join(text_lines)
                    card_list.append(current_card)
                current_card = {'name': '', 'super_type': '', 'sub_type': '', 'mana': '', 'text': '', 'power': '', 'toughness': ''}
                text_lines = []
                in_text_block = False
                continue

            if current_card is None:
                continue

            # Handle multiline rule text collection
            if in_text_block:
                if line.startswith("\t\t") or line.startswith("  "):
                    text_lines.append(clean_tags(line))
                    continue
                else:
                    in_text_block = False
                    if text_lines:
                        current_card['text'] = "\n".join(text_lines)
                        text_lines = []

            # Parse structural lines
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
            elif key == "rule_text":
                in_text_block = True
                if value:
                    text_lines.append(clean_tags(value))

        # Capture last card
        if current_card and current_card.get('name'):
            if text_lines:
                current_card['text'] = "\n".join(text_lines)
            card_list.append(current_card)

    # Process types neatly
    for card in card_list:
        if card['super_type'] and card['sub_type']:
            card['type'] = f"{card['super_type']} — {card['sub_type']}"
        elif card['super_type']:
            card['type'] = card['super_type']
        else:
            card['type'] = "Unknown"

    generate_html(card_list)

    import shutil
    shutil.rmtree(EXTRACT_DIR)
    print(f"Successfully parsed {len(card_list)} cards and updated index.html!")

def generate_html(cards):
    os.makedirs(DOCS_DIR, exist_ok=True)
    html_path = os.path.join(DOCS_DIR, "index.html")
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dota 2 Cube</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: #e0e0e0; padding: 20px; }
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #1e1e1e; border: 2px solid #333; border-radius: 8px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; flex-direction: column; justify-content: space-between; min-height: 200px; }
        .card-header { margin-bottom: 5px; position: relative; }
        .card-name { font-size: 1.2em; font-weight: bold; color: #fff; display: inline-block; max-width: 75%; }
        .card-mana { float: right; color: #ffca28; font-weight: bold; font-size: 1.1em; }
        .card-type { font-style: italic; font-size: 0.9em; color: #aaa; margin-bottom: 10px; border-bottom: 1px solid #444; padding-bottom: 5px; }
        .card-text { font-size: 0.95em; white-space: pre-wrap; line-height: 1.4; color: #ccc; flex-grow: 1; margin-bottom: 10px; }
        .card-pt { text-align: right; font-weight: bold; color: #fff; font-size: 1.1em; }
    </style>
</head>
<body>
    <h1>Dota 2 Cube — Card List</h1>
    <div class="card-grid">
"""
    
    for card in cards:
        pt_display = f"<div class='card-pt'>{card['power']}/{card['toughness']}</div>" if card['power'] or card['toughness'] else ""
        html_content += f"""
        <div class="card">
            <div class="card-header">
                <span class="card-mana">{card['mana']}</span>
                <div class="card-name">{card['name']}</div>
            </div>
            <div class="card-type">{card['type']}</div>
            <div class="card-text">{card['text']}</div>
            {pt_display}
        </div>"""
        
    html_content += """
    </div>
</body>
</html>
"""
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    parse_mse_set()
