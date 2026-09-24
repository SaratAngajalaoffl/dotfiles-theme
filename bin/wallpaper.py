#!/usr/bin/env python3
"""The wallpaper library: every wallpaper is a theme.

Picking a wallpaper applies a colour scheme along with it:

  curated    the wallpaper ships with one of the hand-made themes
             (config/themes/<theme>/backgrounds/), or its manifest entry names
             one with "theme": that theme's palette is used as-is.
  generated  anything else: matugen derives a palette from the image, which
             is rendered through the same templates as the curated themes into
             ~/.local/state/theme/generated/<slug>/, cached until the image
             changes.

Either way theme-set.sh then applies it (symlinks, Qt, kitty, Hyprland, the
shell), with this wallpaper rather than the theme's default one.

Library = config/wallpapers/* plus every theme's backgrounds/. Names and tags
live in config/wallpapers.json, keyed by the image's path relative to config/:

  "wallpapers/tokyo-rain.jpg": {"name": "Tokyo Rain", "tags": ["anime", "cityscape"]}

Optional per entry: "theme" (use that curated palette), "mode" ("dark" /
"light", for generated palettes; detected from the image otherwise). "light"
and "dark" are also added to every wallpaper's tags automatically, from its
mode, so they never need tagging by hand.

Usage:
  wallpaper.py list                      JSON for the shell
  wallpaper.py apply <id>                set wallpaper + colours
  wallpaper.py import <file>... [--tags a,b] [--name N]
                                         copy into the library (dupes skipped)
  wallpaper.py tag <id> <a,b,c>          replace an entry's tags
  wallpaper.py name <id> <name>          rename an entry
  wallpaper.py current                   the applied wallpaper's id
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
CONFIG = os.path.join(HOME, ".config", "theme")
MANIFEST = os.path.join(CONFIG, "wallpapers.json")
LIBRARY = os.path.join(CONFIG, "wallpapers")
THEMES = os.path.join(CONFIG, "themes")
STATE = os.path.join(HOME, ".local", "state", "theme")
GENERATED = os.path.join(STATE, "generated")
CHOSEN = os.path.join(STATE, "wallpaper.json")
THUMBS = os.path.join(HOME, ".cache", "theme", "thumbs")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
THUMB_W = 480

# theme-gen.py sits next to this file (both are symlinked into ~/.local/bin).
_here = os.path.dirname(os.path.realpath(__file__))
_spec = importlib.util.spec_from_file_location("theme_gen", os.path.join(_here, "theme-gen.py"))
theme_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(theme_gen)


# ── Manifest ────────────────────────────────────────────────────────────────
def load_manifest() -> dict:
    try:
        with open(MANIFEST) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_manifest(m: dict) -> None:
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as f:
        json.dump(dict(sorted(m.items())), f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, MANIFEST)


# ── Discovery ───────────────────────────────────────────────────────────────
def discover() -> list[str]:
    """Every wallpaper id (path relative to CONFIG): library, then themes."""
    ids = []
    if os.path.isdir(LIBRARY):
        ids += sorted("wallpapers/" + f for f in os.listdir(LIBRARY)
                      if f.lower().endswith(IMAGE_EXT))
    for theme in sorted(os.listdir(THEMES)):
        bg = os.path.join(THEMES, theme, "backgrounds")
        if os.path.isdir(bg):
            ids += sorted(f"themes/{theme}/backgrounds/{f}" for f in os.listdir(bg)
                          if f.lower().endswith(IMAGE_EXT))
    return ids


def curated_theme(wid: str, entry: dict) -> str | None:
    if entry.get("theme"):
        return entry["theme"]
    m = re.match(r"themes/([^/]+)/backgrounds/", wid)
    return m.group(1) if m else None


def pretty(wid: str) -> str:
    stem = os.path.splitext(os.path.basename(wid))[0]
    return re.sub(r"[-_]+", " ", stem).strip().title()


def slug(wid: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", os.path.splitext(wid)[0].lower()).strip("-")


# ── Images ──────────────────────────────────────────────────────────────────
def thumbnail(path: str, wid: str) -> str:
    """A small JPEG for the picker grid (full-size images are up to 5K)."""
    out = os.path.join(THUMBS, slug(wid) + ".jpg")
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(path):
        return out
    from PIL import Image
    os.makedirs(THUMBS, exist_ok=True)
    with Image.open(path) as im:
        im.seek(0)                       # first frame of a gif
        im = im.convert("RGB")
        im.thumbnail((THUMB_W, THUMB_W))
        im.save(out, "JPEG", quality=85)
    return out


def detect_mode(path: str) -> str:
    """Light if the image is mostly bright, going by mean luminance."""
    from PIL import Image, ImageStat
    with Image.open(path) as im:
        im.seek(0)
        small = im.convert("L").resize((64, 36))
        return "light" if ImageStat.Stat(small).mean[0] > 150 else "dark"


def file_hash(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Generated palettes ──────────────────────────────────────────────────────
def _hex(c: str) -> tuple[float, float, float]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _to_hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0, min(1, v)) * 255):02x}" for v in rgb)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _hex(a), _hex(b)
    return _to_hex([x + (y - x) * t for x, y in zip(ra, rb)])


def harmonize(ref: str, source: str) -> str:
    """Nudge `ref`'s hue towards `source`'s (at most 15°, half the gap), as
    Material's harmonize does: terminal red stays red, but belongs."""
    h1, l1, s1 = colorsys.rgb_to_hls(*_hex(ref))
    h2, _, s2 = colorsys.rgb_to_hls(*_hex(source))
    if s2 < 0.08:                        # greyscale source: nothing to lean to
        return ref
    diff = ((h2 - h1 + 0.5) % 1.0) - 0.5
    step = max(-15 / 360, min(15 / 360, diff * 0.5))
    return _to_hex(colorsys.hls_to_rgb((h1 + step) % 1.0, l1, s1))


# The hue slots take Catppuccin's (mocha for dark, latte for light) and lean
# them towards the wallpaper; the accent slots take the wallpaper's own.
HUE_SLOTS = ["rosewater", "flamingo", "pink", "mauve", "red", "maroon", "peach",
             "yellow", "green", "teal", "sky"]


def matugen(path: str, mode: str) -> dict[str, str]:
    out = subprocess.run(
        ["matugen", "image", path, "--dry-run", "-j", "hex", "-m", mode,
         "--source-color-index", "0", "-q"],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out[out.find("{"):])
    return {k: v[mode]["color"] for k, v in data["colors"].items()}


def generate_palette(path: str, mode: str) -> dict[str, str]:
    c = matugen(path, mode)
    ref = theme_gen.load_palette("catppuccin-mocha" if mode == "dark" else "catppuccin-latte")
    p = {k: harmonize(ref[k], c["primary"]) for k in HUE_SLOTS}
    p.update(blue=c["primary"], lavender=c["secondary"], sapphire=c["tertiary"])

    if mode == "dark":
        p.update(
            base=c["surface"],
            mantle=c["surface_container_lowest"],
            crust=mix(c["surface_container_lowest"], "#000000", 0.35),
            surface0=c["surface_container"],
            surface1=c["surface_container_high"],
            surface2=c["surface_container_highest"],
        )
    else:
        p.update(
            base=c["surface"],
            mantle=c["surface_container"],
            crust=c["surface_container_high"],
            surface0=c["surface_container_highest"],
            surface1=c["surface_dim"],
            surface2=mix(c["surface_dim"], c["outline_variant"], 0.5),
        )
    p.update(
        overlay0=c["outline_variant"],
        overlay1=mix(c["outline_variant"], c["outline"], 0.5),
        overlay2=c["outline"],
        subtext0=mix(c["outline"], c["on_surface_variant"], 0.5),
        subtext1=c["on_surface_variant"],
        text=c["on_surface"],
    )
    return {k: p[k] for k in theme_gen.PALETTE_KEYS}


def qt_colors(p: dict[str, str]) -> str:
    """qt5ct/qt6ct colour scheme: 22 roles per state, in QPalette order."""
    def row(*keys):
        return ", ".join(k if k.startswith("#") else "#ff" + p[k].lstrip("#")
                         for k in keys)
    ph = "#80" + p["overlay0"].lstrip("#")
    return "[ColorScheme]\n" + "\n".join([
        "active_colors=" + row("text", "surface1", "surface2", "surface0", "crust", "mantle",
                               "text", "text", "text", "base", "mantle", "crust", "blue",
                               "crust", "blue", "lavender", "mantle", "#ffffffff", "base",
                               "text", ph, "blue"),
        "inactive_colors=" + row("overlay1", "base", "surface1", "surface0", "crust", "mantle",
                                 "overlay1", "text", "overlay1", "base", "mantle", "crust",
                                 "surface0", "overlay1", "overlay1", "overlay1", "mantle",
                                 "#ffffffff", "base", "text", ph, "surface0"),
        "disabled_colors=" + row("overlay0", "surface0", "surface1", "surface0", "crust",
                                 "mantle", "overlay0", "text", "overlay0", "base", "mantle",
                                 "crust", "mantle", "overlay0", "overlay0", "overlay0",
                                 "mantle", "#ffffffff", "base", "text", ph, "mantle"),
    ]) + "\n"


def generated_theme(wid: str, path: str, entry: dict) -> str:
    """The generated theme dir for a wallpaper, (re)built if missing/stale."""
    out = os.path.join(GENERATED, slug(wid))
    stamp = os.path.join(out, ".source")
    mode = entry.get("mode") or detect_mode(path)
    key = f"{file_hash(path)} {mode}"
    if os.path.exists(stamp) and open(stamp).read() == key:
        return out

    palette = generate_palette(path, mode)
    name = entry.get("name") or pretty(wid)
    conf = {
        "THEME_NAME": name, "THEME_MODE": mode,
        "BORDER_ACCENT": "blue", "BORDER_INACTIVE": "overlay1",
        "GENERATOR": "omarchy", "ACTIVE_ALPHA": "cc", "INACTIVE_ALPHA": "aa",
        "KITTY_NAME": f"wallpaper {name}", "KITTY_UPSTREAM": "generated",
    }
    tmp = out + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.join(tmp, "backgrounds"))
    theme_gen.render_outputs(theme_gen.build_context_from(slug(wid), palette, conf, tmp), tmp)
    with open(os.path.join(tmp, "palette.json"), "w") as f:
        json.dump(palette, f, indent=2)
    with open(os.path.join(tmp, "qt-colors.conf"), "w") as f:
        f.write(qt_colors(palette))
    conf["QT_SCHEME_PATH"] = os.path.join(out, "qt-colors.conf")
    with open(os.path.join(tmp, "theme.conf"), "w") as f:
        f.writelines(f'{k}="{v}"\n' for k, v in conf.items())
    os.symlink(path, os.path.join(tmp, "backgrounds", os.path.basename(path)))
    with open(os.path.join(tmp, ".source"), "w") as f:
        f.write(key)
    shutil.rmtree(out, ignore_errors=True)
    os.replace(tmp, out)
    return out


# ── Commands ────────────────────────────────────────────────────────────────
def resolve(wid: str) -> tuple[str, dict]:
    path = os.path.join(CONFIG, wid)
    if not os.path.isfile(path):
        sys.exit(f"wallpaper.py: no such wallpaper: {wid}")
    return path, load_manifest().get(wid, {})


def current() -> str:
    try:
        with open(CHOSEN) as f:
            return json.load(f).get("id", "")
    except (OSError, ValueError):
        return ""


def cmd_list(_args) -> int:
    manifest = load_manifest()
    items = []
    for wid in discover():
        path = os.path.join(CONFIG, wid)
        entry = manifest.get(wid, {})
        theme = curated_theme(wid, entry)
        palette, mode = None, entry.get("mode")
        if theme:
            palette = theme_gen.load_palette(theme)
            mode = theme_gen.load_conf(theme).get("THEME_MODE", "dark")
        else:
            gen = os.path.join(GENERATED, slug(wid), "palette.json")
            if os.path.exists(gen):
                palette = json.load(open(gen))
            mode = mode or detect_mode(path)
        tags = list(dict.fromkeys(entry.get("tags", []) + [mode]))
        items.append({
            "id": wid,
            "name": entry.get("name") or pretty(wid),
            "path": path,
            "thumb": thumbnail(path, wid),
            "tags": tags,
            "mode": mode,
            "theme": theme or "",
            "swatch": [palette[k] for k in ("base", "surface0", "text", "blue", "red",
                                            "yellow", "green", "mauve")] if palette else [],
        })
    json.dump({"current": current(), "wallpapers": items}, sys.stdout, ensure_ascii=False)
    return 0


def cmd_apply(args) -> int:
    path, entry = resolve(args.id)
    theme = curated_theme(args.id, entry)
    root = os.path.join(THEMES, theme) if theme else generated_theme(args.id, path, entry)

    os.makedirs(STATE, exist_ok=True)
    with open(CHOSEN, "w") as f:
        json.dump({"id": args.id, "path": path, "theme": root}, f)

    env = dict(os.environ, WALLPAPER=path, THEME_QUIET="1")
    return subprocess.run([os.path.join(_here, "theme-set.sh"), root], env=env).returncode


def cmd_import(args) -> int:
    os.makedirs(LIBRARY, exist_ok=True)
    manifest = load_manifest()
    known = {file_hash(os.path.join(CONFIG, w)): w for w in discover()}
    tags = [t.strip().lower() for t in (args.tags or "").split(",") if t.strip()]
    for src in args.files:
        h = file_hash(src)
        if h in known:
            print(f"skip {src}: already in the library as {known[h]}")
            continue
        base = os.path.basename(src)
        dest = os.path.join(LIBRARY, base)
        n = 1
        while os.path.exists(dest):
            stem, ext = os.path.splitext(base)
            dest = os.path.join(LIBRARY, f"{stem}-{n}{ext}")
            n += 1
        shutil.copy2(src, dest)
        wid = "wallpapers/" + os.path.basename(dest)
        entry = {"tags": tags}
        if args.name and len(args.files) == 1:
            entry["name"] = args.name
        manifest[wid] = entry
        known[h] = wid
        print(f"added {wid} ({detect_mode(dest)})")
    save_manifest(manifest)
    return 0


def cmd_tag(args) -> int:
    resolve(args.id)
    manifest = load_manifest()
    entry = manifest.setdefault(args.id, {})
    # light/dark are derived from the mode; don't store them as tags.
    entry["tags"] = [t for t in dict.fromkeys(
        t.strip().lower() for t in args.tags.split(",") if t.strip())
        if t not in ("light", "dark")]
    save_manifest(manifest)
    return 0


def cmd_name(args) -> int:
    resolve(args.id)
    manifest = load_manifest()
    manifest.setdefault(args.id, {})["name"] = args.name
    save_manifest(manifest)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("current").set_defaults(fn=lambda a: print(current()) or 0)
    p = sub.add_parser("apply"); p.add_argument("id"); p.set_defaults(fn=cmd_apply)
    p = sub.add_parser("import"); p.add_argument("files", nargs="+")
    p.add_argument("--tags"); p.add_argument("--name"); p.set_defaults(fn=cmd_import)
    p = sub.add_parser("tag"); p.add_argument("id"); p.add_argument("tags"); p.set_defaults(fn=cmd_tag)
    p = sub.add_parser("name"); p.add_argument("id"); p.add_argument("name"); p.set_defaults(fn=cmd_name)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
