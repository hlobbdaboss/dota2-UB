import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
xml_path = BASE / "Dota2UniversesBeyond-cockatrice.xml"
content = xml_path.read_text(encoding="utf-8")

basics = [
    ("Plains", "W"),
    ("Island", "U"),
    ("Swamp", "B"),
    ("Mountain", "R"),
    ("Forest", "G"),
]

TEMPLATE = """  <card>
   <name>{name}</name>
   <text>({{T}}: Add {{{color}}}.)</text>
   <prop>
   <layout>normal</layout>
   <side>front</side>
   <type>Basic Land — {name}</type>
   <maintype>Land</maintype>
   <cmc>0</cmc>
   <coloridentity>{color}</coloridentity>
   </prop>
   <set rarity="basic land" num="{num:04d}" picurl="https://api.scryfall.com/cards/named?exact={name}&amp;format=image">DUB</set>
   <tablerow>0</tablerow>
  </card>
"""

start_num = 340
blocks = ""
for i, (name, color) in enumerate(basics):
    blocks += TEMPLATE.format(name=name, color=color, num=start_num + i)

# insert right before closing </cards>
assert content.count("</cards>") == 1
content = content.replace("</cards>", blocks + " </cards>")

xml_path.write_text(content, encoding="utf-8")
print("inserted", len(basics), "basic lands")

# sanity check well-formed XML
import xml.etree.ElementTree as ET
tree = ET.parse(xml_path)
root = tree.getroot()
names = [c.find("name").text for c in root.find("cards").findall("card")]
print("total cards now:", len(names))
for b, _ in basics:
    print(b, "present:", b in names)
