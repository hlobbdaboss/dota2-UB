import os
import zipfile

MSE_FILE_PATH = "/Users/Harrison_1/Desktop/Full-Magic-Pack-main/Sets/Dota Set.mse-set"
EXTRACT_DIR = "./temp_mse"
DOCS_DIR = "./docs"

def parse_mse_set():
    if not os.path.exists(MSE_FILE_PATH):
        print(f"Error: Could not find MSE file at {MSE_FILE_PATH}")
        return

    print("Extracting MSE set file...")
    with zipfile.ZipFile(MSE_FILE_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    set_data_path = os.path.join(EXTRACT_DIR, "set")
    if not os.path.exists(set_data_path):
        print("Error: 'set' data file not found inside the mse-set archive.")
        return

    print("Parsing card data dynamically...")
    card_list = []
    current_card = None
    in_text_block = False
    text_lines = []

    with open(set_data_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # Detect a new card block
            if line.startswith("card:"):
                if current_card and 'name' in current_card:
                    if text_lines:
                        current_card['text'] = "\n".join(text_lines).strip()
                    card_list.append(current_card)
                current_card = {'name': '', 'type': 'Unknown', 'mana': '', 'text': ''}
                text_lines = []
                in_text_block = False
                continue

            # If we haven't hit the first card yet, ignore global set properties
            if current_card is None:
                continue

            # Handle lines inside a multiline text block
            if in_text_block:
                if line.startswith("\t\t") or line.startswith("  "):
                    text_lines.append(line.strip())
                    continue
                else:
                    in_text_block = False
                    if text_lines:
                        current_card['text'] = "\n".join(text_lines).strip()
                        text_lines = []

            # Parse key-value pairs (handling both tabs and double-spaces)
            stripped = line.strip()
            if not stripped:
                continue

            if line.startswith("\t") or line.startswith("  "):
                if ":" in stripped:
                    key, value = stripped.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if key == "name":
                        current_card['name'] = value
                    elif key == "type":
                        current_card['type'] = value
                    elif key == "casting cost":
                        current_card['mana'] = value
                    elif key == "text":
                        in_text_block = True
                        if value:  # If text starts on the same line
                            text_lines.append(value)

        # Add the final card if left over
        if current_card and 'name' in current_card:
            if text_lines:
                current_card['text'] = "\n".join(text_lines).strip()
            card_list.append(current_card)

    # Filter out empty entries or structural templates
    card_list = [c for c in card_list if c['name'].strip()]

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
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .card { background: #1e1e1e; border: 2px solid #333; border-radius: 8px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; flex-direction: column; justify-content: space-between; min-height: 150px; }
        .card-header { margin-bottom: 5px; }
        .card-name { font-size: 1.2em; font-weight: bold; color: #fff; display: inline-block; max-width: 70%; }
        .card-mana { float: right; color: #ffca28; font-weight: bold; font-size: 1.1em; }
        .card-type { font-style: italic; font-size: 0.9em; color: #aaa; margin-bottom: 10px; border-bottom: 1px solid #444; padding-bottom: 5px; }
        .card-text { font-size: 0.95em; white-space: pre-wrap; line-height: 1.4; color: #ccc; flex-grow: 1; }
    </style>
</head>
<body>
    <h1>Dota 2 Cube — Card List</h1>
    <div class="card-grid">
"""
    
    for card in cards:
        html_content += f"""
        <div class="card">
            <div class="card-header">
                <span class="card-mana">{card['mana']}</span>
                <div class="card-name">{card['name']}</div>
            </div>
            <div class="card-type">{card['type']}</div>
            <div class="card-text">{card['text']}</div>
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
