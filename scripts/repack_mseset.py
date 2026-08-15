import zipfile, shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
mse_path = BASE / "mse" / "Dota 2 Universes Beyond.mse-set"
edited_set = BASE / "scripts" / "edited_set_data.txt"
tmp_path = BASE / "mse" / "Dota 2 Universes Beyond.mse-set.new"

new_set_bytes = edited_set.read_bytes()

with zipfile.ZipFile(mse_path, "r") as zin:
    names = zin.namelist()
    assert "set" in names
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "set":
                data = new_set_bytes
            zout.writestr(item, data)

# swap in place
tmp_path.replace(mse_path)
print("repacked OK, new size:", mse_path.stat().st_size)
