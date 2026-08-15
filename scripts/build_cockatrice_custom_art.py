import json, shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
rename_map = json.load(open(BASE / "scripts" / "custom_art_rename_map.json", encoding="utf-8"))
src_dir = BASE / "Card Arts Full"
dest_dir = BASE / "Cockatrice Custom Art"
dest_dir.mkdir(exist_ok=True)

copied, missing = [], []
for dest_name, src_name in rename_map.items():
    src = src_dir / src_name
    dest = dest_dir / dest_name
    if src.exists():
        shutil.copyfile(src, dest)
        copied.append(dest_name)
    else:
        missing.append((dest_name, src_name))

print("copied:", len(copied))
print("missing:", len(missing))
for m in missing:
    print("  MISSING:", m)
