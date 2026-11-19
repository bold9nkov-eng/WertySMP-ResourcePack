#!/usr/bin/env python3
"""Build the VoidMain 1.21.11 resource pack with galaxy GUI tiles and rarity scroll models."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image, ImageEnhance, ImageOps
import json, shutil, tempfile

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "VoidMain-ResourcePack-1.21.11-v1.5-CUSTOM-ENCHANT-SOUNDS.zip"
GALAXY = ROOT / "assets/voidmain/textures/gui/galaxy.png"
OUT = ROOT / "VoidMain-ResourcePack-1.21.11-v1.6-GALAXY-VE.zip"
if not BASE.exists() or not GALAXY.exists():
    raise SystemExit("Missing base v1.5 pack or galaxy.png")

with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp) / "pack"
    work.mkdir()
    with ZipFile(BASE) as z:
        z.extractall(work)

    def write_json(rel, data):
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 54 individually cropped galaxy tiles, mapped to filler panes in /ve.
    galaxy = Image.open(GALAXY).convert("RGBA")
    w, h = galaxy.size
    for slot in range(54):
        col, row = slot % 9, slot // 9
        x0, x1 = round(col*w/9), round((col+1)*w/9)
        y0, y1 = round(row*h/6), round((row+1)*h/6)
        tile = galaxy.crop((x0, y0, x1, y1)).resize((32, 32), Image.Resampling.LANCZOS)
        tile = ImageEnhance.Brightness(tile).enhance(0.82)
        name = f"gui_galaxy_tile_{slot}"
        tex = work / f"assets/voidmain/textures/item/gui/{name}.png"
        tex.parent.mkdir(parents=True, exist_ok=True)
        tile.save(tex, optimize=True)
        write_json(f"assets/voidmain/items/{name}.json", {
            "model": {"type": "minecraft:model", "model": f"voidmain:item/{name}"}
        })
        write_json(f"assets/voidmain/models/item/{name}.json", {
            "parent": "minecraft:item/generated",
            "textures": {"layer0": f"voidmain:item/gui/{name}"}
        })

    # Six distinct scroll appearances: uncommon, rare, epic, legendary, divine, admin.
    original_path = work / "assets/voidmain/textures/item/enchant_scroll.png"
    original = Image.open(original_path).convert("RGBA")
    tints = {
        0: (255, 70, 90),      # admin
        1: (255, 210, 110),    # divine
        2: (255, 150, 55),     # legendary
        3: (177, 92, 255),     # epic
        4: (80, 190, 255),     # rare
        5: (100, 225, 150),    # uncommon
    }
    for tier, rgb in tints.items():
        overlay = Image.new("RGBA", original.size, (*rgb, 0))
        overlay.putalpha(original.getchannel("A"))
        # Preserve the ink/details while applying a tier-specific color wash.
        tinted = Image.blend(original, overlay, 0.48)
        tex = work / f"assets/voidmain/textures/item/scroll_tier_{tier}.png"
        tinted.save(tex, optimize=True)
        write_json(f"assets/voidmain/items/scroll_tier_{tier}.json", {
            "model": {"type": "minecraft:model", "model": f"voidmain:item/scroll_tier_{tier}"}
        })
        write_json(f"assets/voidmain/models/item/scroll_tier_{tier}.json", {
            "parent": "minecraft:item/generated",
            "textures": {"layer0": f"voidmain:item/scroll_tier_{tier}"}
        })

    mcmeta = json.loads((work / "pack.mcmeta").read_text(encoding="utf-8"))
    mcmeta["pack"]["description"] = "VoidMain | Galaxy /ve • 6 Scroll Rarities • 1.21.11"
    (work / "pack.mcmeta").write_text(json.dumps(mcmeta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if OUT.exists():
        OUT.unlink()
    with ZipFile(OUT, "w", ZIP_DEFLATED, compresslevel=9) as z:
        for path in work.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(work).as_posix())

print(f"Built {OUT.name} ({OUT.stat().st_size} bytes)")
