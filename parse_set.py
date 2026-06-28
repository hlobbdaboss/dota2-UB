import os
import zipfile
import re

# The path to your master MSE file
MSE_FILE_PATH = "/Users/Harrison_1/Desktop/Full-Magic-Pack-main/Sets/Dota Set.mse-set"
# Where to extract files temporarily
EXTRACT_DIR = "./temp_mse"
# Where your GitHub Pages live
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

    print("Parsing card data...")
    with open(set_data_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Split the file by individual card blocks
    cards_raw = content.split("card:\n")
    card_list = []

    for card_block in cards_raw[1:]:  # Skip the header info before the first card
        card_info = {}
        
        # Simple regex helpers to pull common card fields
        name_match = re.search(r"^\s*name:\s*(.*)$", card_block, re.MULTILINE)
        type_match = re.search(r"^\s*type:\s*(.*)$", card_block, re.MULTILINE)
        mana_match = re.search(r"^\s*casting cost:\s*(.*)$", card_block, re.MULTILINE)
        text_match = re.search(r"^\s*text:\s*\n((?:\s{2,}.*\n)*)", card_block, re.MULTILINE)

        if name_match:
            card_info['name'] = name_match.group(1).strip()
            card_info['type'] = type_match.group(1).strip() if type_match else "Unknown"
            card_info['mana'] = mana_match.group(1).strip() if mana_match else ""
            
            # Clean up the multiline card text formatting from MSE
            if text_match:
                raw_text = text_match.group(1)
                clean_text = "\n".join([line.strip() for line in raw_text.split("\n")])
                card_info['text'] = clean_text.strip()
            else:
                card_info['text'] = ""
                
            card_list.append(card_info)

    # Generate a new index.html with the parsed card data
    generate_html(card_list)

    # Clean up temporary extracted files
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
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }
        .card { background: #1e1e1e; border: 2px solid #333; border-radius: 8px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .card-name { font-size: 1.2em; font-weight: bold; margin-bottom: 5px; color: #fff; }
        .card-mana { float: right; color: #ffca28; }
        .card-type { font-style: italic; font-size: 0.9em; color: #aaa; margin-bottom: 10px; border-bottom: 1px solid #444; padding-bottom: 5px; }
        .card-text { font-size: 0.95em; white-space: pre-wrap; line-height: 1.4; }
    </style>
</head>
<body>
    <h1>Dota 2 Cube — Card List</h1>
    <div class="card-grid">
"""
    
    for card in cards:
        html_content += f"""
        <div class="card">
            <span class="card-mana">{card['mana']}</span>
            <div class="card-name">{card['name']}</div>
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
