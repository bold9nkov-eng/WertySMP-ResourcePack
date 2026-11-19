#!/usr/bin/env python3
"""Build the VoidMain 1.21.11 resource pack with rarity-colored scroll models and sounds."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image, ImageOps
import json, shutil, tempfile, base64

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "VoidMain-ResourcePack-1.21.11-v1.5-CUSTOM-ENCHANT-SOUNDS.zip"

OUT = ROOT / "VoidMain-ResourcePack-1.21.11-v1.7-COLORED-SCROLLS.zip"
if not BASE.exists():
    raise SystemExit("Missing base v1.5 resource pack")

with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp) / "pack"
    work.mkdir()
    # The archived v1.5 source is a wrapper ZIP containing the actual pack ZIP.
    # Unwrap it before editing, otherwise the final resource pack becomes ZIP-in-ZIP
    # and Minecraft cannot see pack.mcmeta at the archive root.
    with ZipFile(BASE) as z:
        entries = [n for n in z.namelist() if not n.endswith("/")]
        nested_zips = [n for n in entries if n.lower().endswith(".zip")]
        if len(entries) == 1 and len(nested_zips) == 1:
            inner_path = Path(tmp) / "base-resource-pack.zip"
            inner_path.write_bytes(z.read(nested_zips[0]))
            with ZipFile(inner_path) as inner:
                inner.extractall(work)
        else:
            z.extractall(work)

    if not (work / "pack.mcmeta").is_file():
        raise SystemExit("Invalid base resource pack: pack.mcmeta is not at the pack root")

    def write_json(rel, data):
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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


    # Procedural original sound design. Each sound is synthesized (not copied from Minecraft)
    # as a short layered effect, then encoded to OGG Vorbis for Java resource packs.
    import math, random, struct, subprocess, wave
    SOUND_SPECS = {
      "vampirism": ("gulp", 0.85), "ice_blade": ("crystal", 0.90),
      "venom": ("acid", 0.95), "execution": ("anvil", 1.25),
      "thor": ("thunder", 1.55), "black_hole": ("suction", 1.55),
      "world_eater": ("roar", 1.85), "godslayer": ("divine", 1.9),
      "moon": ("chime", 0.75), "berserk": ("roar", 1.25),
      "spear_dash": ("whoosh", 0.85), "rebound": ("boing", 0.75),
      "hook": ("harpoon", 0.9), "phantom_blade": ("ghost", 0.9),
      "titan_shield": ("anvil", 1.2), "reflection": ("clang", 0.9),
      "second_wind": ("rise", 1.0), "immortality": ("totem", 1.35),
      "soft_paws": ("soft", 0.45), "immunity": ("steam", 0.75),
      "lava_walk": ("steam", 0.9), "water_walk": ("ice", 0.8),
      "magnet": ("pickup", 0.6), "auto_smelt": ("fire", 0.7),
      "lumberjack": ("wood", 0.85), "drill": ("grind", 1.0),
      "chain_mining": ("collapse", 1.15), "swift_mining": ("whoosh", 0.65),
      "experience": ("xp", 0.7), "glide": ("wind", 0.5),
      "wings": ("feather", 0.55), "aerodynamics": ("whoosh", 0.8),
      "double_jump": ("boing", 0.75), "shadow": ("ghost", 0.8),
      "enchant_apply": ("magic", 0.85), "enchant_fail": ("fail", 0.8),
      "disenchant": ("tear", 0.9), "book_get": ("treasure", 1.0),
      "ability_cast": ("bow", 0.85)
    }
    SR = 24000
    def synth(kind, duration, seed):
        rng = random.Random(seed)
        n = int(SR * duration)
        samples = []
        phases = [0.0, 0.0, 0.0]
        for i in range(n):
            t = i / SR
            x = t / duration
            env = min(1.0, x * 12) * min(1.0, (1-x) * 7)
            noise = rng.uniform(-1, 1)
            if kind in ("gulp", "acid", "steam"):
                freq = 115 + 90*x + 28*math.sin(2*math.pi*7*t)
                v = .45*math.sin(2*math.pi*freq*t) + .28*noise*(1 if kind != "gulp" else .35)
                if kind == "acid": v += .22*math.sin(2*math.pi*(850-500*x)*t)
            elif kind in ("crystal", "ice", "chime", "divine", "treasure", "magic", "xp", "totem"):
                f = [880, 1320, 1760][int(x*3)%3]
                v = .48*math.sin(2*math.pi*f*t) + .22*math.sin(2*math.pi*f*2.01*t)
                v *= (1-x*.55)
                if kind in ("ice", "crystal"): v += .12*noise*max(0,1-x*2)
            elif kind in ("thunder", "collapse", "roar", "anvil", "clang", "grind"):
                f = (65 if kind in ("thunder","roar","collapse") else 130) * (1+2*x)
                v = .55*math.sin(2*math.pi*f*t) + .30*noise
                if kind in ("thunder","roar","collapse"): v += .18*math.sin(2*math.pi*38*t)
            elif kind in ("suction", "ghost"):
                f = 520 - 420*x
                v = .42*math.sin(2*math.pi*f*t) + .28*noise*(1-x)
            elif kind in ("whoosh", "wind", "feather", "soft", "tear", "wood", "fire"):
                v = .55*noise*(math.sin(math.pi*x)**.7)
                v += .12*math.sin(2*math.pi*(300+700*x)*t)
            elif kind in ("boing", "bow", "harpoon", "pickup"):
                f = (180 if kind=="boing" else 420) * (1+3*x)
                v = .5*math.sin(2*math.pi*f*t) + .16*noise
            elif kind in ("rise", "fail"):
                f = (180+650*x) if kind=="rise" else (650-450*x)
                v = .42*math.sin(2*math.pi*f*t) + .12*noise
            else:
                v = .35*math.sin(2*math.pi*(220+500*x)*t) + .15*noise
            # gentle transient and soft limiter
            v *= env
            v = math.tanh(v*1.7) * 0.72
            samples.append(struct.pack("<h", int(max(-1,min(1,v))*32767)))
        return b"".join(samples)

    sound_events = {}
    for idx, (name, (kind, volume)) in enumerate(SOUND_SPECS.items()):
        rel = f"assets/voidmain/sounds/enchant/{name}.ogg"
        out = work / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        duration = 1.35 if kind in ("thunder","roar","divine","totem","anvil","collapse") else 0.82
        wav_path = Path(tmp) / f"{name}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
            wf.writeframes(synth(kind, duration, 7400+idx))
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(wav_path),"-c:a","libvorbis","-q:a","5",str(out)], check=True)
        sound_events[f"enchant.{name}"] = {
          "category": "player",
          "sounds": [{"name": f"voidmain:enchant/{name}", "volume": volume, "pitch": 1.0}]
        }
    write_json("assets/voidmain/sounds.json", sound_events)

    # Particle sprite sheets are intentionally small and high-contrast. The plugin
    # drives the corresponding vanilla dust/crit/portal particle packets in-game.
    particle_dir = work / "assets/voidmain/textures/particle"
    particle_dir.mkdir(parents=True, exist_ok=True)
    from PIL import ImageDraw, ImageFilter
    for pname, color in {
      "void_spark": (184, 92, 255, 255), "frost_shard": (120, 220, 255, 255),
      "venom_mote": (120, 255, 105, 255), "solar_glint": (255, 218, 120, 255),
      "blood_mote": (220, 35, 75, 255), "wind_streak": (220, 235, 255, 210)
    }.items():
        im = Image.new("RGBA", (16,16), (0,0,0,0))
        d = ImageDraw.Draw(im)
        d.ellipse((5,5,10,10), fill=color)
        im = im.filter(ImageFilter.GaussianBlur(2.0))
        im.save(particle_dir / f"{pname}.png", optimize=True)

    readme = work / "VOIDMAIN-CUSTOM-SOUNDS.txt"
    readme_lines = [
        "VoidMain custom enchantment sound events (namespace voidmain):",
        *[f"enchant.{k}" for k in SOUND_SPECS],
        "",
        'Play from plugin with: player.playSound(location, "voidmain:enchant.vampirism", volume, 1.0f)',
        "Sound files are original procedural synth effects generated during the build.",
        "Particle PNGs are visual resources; the Bukkit plugin must emit supported vanilla particles (DUST, CRIT, PORTAL, etc.) to create live effects."
    ]
    readme.write_text("\\n".join(readme_lines) + "\\n", encoding="utf-8")

    mcmeta = json.loads((work / "pack.mcmeta").read_text(encoding="utf-8"))
    mcmeta["pack"]["description"] = "VoidMain | Galaxy /ve • 6 Scroll Rarities • Custom Enchant Sounds • 1.21.11"
    (work / "pack.mcmeta").write_text(json.dumps(mcmeta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if OUT.exists():
        OUT.unlink()
    with ZipFile(OUT, "w", ZIP_DEFLATED, compresslevel=9) as z:
        for path in work.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(work).as_posix())

print(f"Built {OUT.name} ({OUT.stat().st_size} bytes)")
