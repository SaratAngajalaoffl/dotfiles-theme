#!/usr/bin/env python3
"""Generate per-app theme files from a theme's palette.

A theme directory is a 26-key palette plus wallpapers; every per-app file
(waybar colors, kitty theme, rofi colors, dunstrc, hyprland borders, nvim
palette, quickshell palette) is derived from that palette via a shared template.

Resolution order:
  1. palette   <- palette.json
  2. patch     <- overrides/palette.json, a partial merge on top
  3. render    <- templates/<file>.tpl
  4. verbatim  <- overrides/<file>, used as-is if present

Step 4 is the escape hatch: drop a whole hand-tuned file in overrides/ and it
wins outright, no templating involved.

Usage:
  theme-gen.py                  # generate every theme in-place
  theme-gen.py --check          # verify generated output matches the tree
  theme-gen.py --theme gruvbox  # single theme
  theme-gen.py --templates      # re-derive templates from the reference theme
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
THEMES_DIR = os.path.join(ROOT, "config", "themes")
TEMPLATES_DIR = os.path.join(ROOT, "templates")

# Reference theme the templates are derived from. Must be the most complete one.
REFERENCE = "catppuccin-mocha"

# template file -> generated filename
# Only the apps that are still part of the desktop. waybar, rofi, dunst and eww
# were replaced by Quickshell and their generated files (waybar-colors.css,
# rofi-colors.rasi, dunstrc, eww-colors.scss) were removed with them — keep
# this list in sync with what actually consumes a themed file.
OUTPUTS = {
    "kitty-theme.conf.tpl":    "kitty-theme.conf",
    "hyprland-colors.lua.tpl": "hyprland-colors.lua",
    "nvim-colors.lua.tpl":     "nvim-colors.lua",
    "quickshell-colors.json.tpl": "quickshell-colors.json",
}

# Palette keys, in the canonical order used by every output file.
PALETTE_KEYS = [
    "rosewater", "flamingo", "pink", "mauve", "red", "maroon", "peach",
    "yellow", "green", "teal", "sky", "sapphire", "blue", "lavender",
    "text", "subtext1", "subtext0", "overlay2", "overlay1", "overlay0",
    "surface2", "surface1", "surface0", "base", "mantle", "crust",
]


def theme_dirs() -> list[str]:
    return sorted(
        d for d in os.listdir(THEMES_DIR)
        if os.path.isdir(os.path.join(THEMES_DIR, d))
    )


def load_conf(theme: str) -> dict[str, str]:
    """Read theme.conf (KEY="value" lines)."""
    conf = {}
    path = os.path.join(THEMES_DIR, theme, "theme.conf")
    if not os.path.exists(path):
        return conf
    for line in open(path):
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        conf[key.strip()] = val.strip().strip('"')
    return conf


def load_palette(theme: str) -> dict[str, str]:
    """The theme's 26-colour palette.

    palette.json is the source of truth. It started life as a migration path
    from waybar-colors.css, which is where the palette used to live — waybar is
    gone now, so the palette had to move somewhere independent of a dead app
    before that file could be deleted.
    """
    pj = os.path.join(THEMES_DIR, theme, "palette.json")
    if not os.path.exists(pj):
        raise FileNotFoundError(
            f"{theme}: no palette.json (every theme needs one — see README)")
    with open(pj) as f:
        return json.load(f)


def resolve_accent(theme_dir: str, palette: dict, conf: dict) -> str:
    """Border accent as a bare 6-hex string (no '#')."""
    return _resolve_border(theme_dir, palette, conf, "ACCENT", "blue",
                           "active_border")


def resolve_inactive(theme_dir: str, palette: dict, conf: dict) -> str:
    """Inactive border colour as a bare 6-hex string (no '#')."""
    return _resolve_border(theme_dir, palette, conf, "INACTIVE", "overlay1",
                           "inactive_border")


def _resolve_border(theme_dir: str, palette: dict, conf: dict,
                    what: str, default_key: str, field: str) -> str:
    # Explicit literal wins (themes whose value falls outside the palette).
    if conf.get(f"BORDER_{what}_HEX"):
        return conf[f"BORDER_{what}_HEX"].lstrip("#").lower()

    key = conf.get(f"BORDER_{what}", default_key)
    if key in palette:
        return palette[key].lstrip("#").lower()

    # Fall back to whatever the existing file says, then to the default key.
    lua = os.path.join(theme_dir, "hyprland-colors.lua")
    if os.path.exists(lua):
        m = re.search(rf'{field}\s*=\s*"rgba\(([0-9a-fA-F]{{6}})', open(lua).read())
        if m:
            return m.group(1).lower()
    return palette.get(default_key, "#7f849c").lstrip("#").lower()


def build_context(theme: str) -> dict[str, str]:
    palette = load_palette(theme)
    conf = load_conf(theme)

    # 2. merge overrides/palette.json
    patch = os.path.join(THEMES_DIR, theme, "overrides", "palette.json")
    if os.path.exists(patch):
        with open(patch) as f:
            palette.update(json.load(f))

    return build_context_from(theme, palette, conf, os.path.join(THEMES_DIR, theme))


def build_context_from(slug: str, palette: dict, conf: dict, theme_dir: str) -> dict[str, str]:
    """Template context for any palette, including ones generated outside
    config/themes/ (wallpaper.py renders generated themes through this)."""
    name = conf.get("THEME_NAME") or slug
    mode = conf.get("THEME_MODE", "dark")
    accent = resolve_accent(theme_dir, palette, conf)
    inactive = resolve_inactive(theme_dir, palette, conf)

    # Which upstream the theme was ported from. Drives the kitty header and
    # the hypr border header style (catppuccin writes its display name,
    # omarchy writes the slug).
    generator = conf.get("GENERATOR", "catppuccin" if slug.startswith("catppuccin") else "omarchy")
    is_catppuccin = generator == "catppuccin"

    kitty_name = conf.get("KITTY_NAME") or (
        "Catppuccin Kitty " + slug.split("-")[-1].capitalize()
        if is_catppuccin else "omarchy " + slug)
    # kitty's upstream URL ends in the flavour name (catppuccin) or the slug.
    kitty_upstream = conf.get("KITTY_UPSTREAM") or (
        slug.split("-")[-1] if is_catppuccin else slug)
    hypr_header = conf.get("HYPR_HEADER") or (name if is_catppuccin else slug)
    # nvim's header always uses the display name, for both generators.
    nvim_header = conf.get("NVIM_HEADER") or name

    ctx = {k: v for k, v in palette.items()}
    ctx.update({
        "NAME":    name,
        "SLUG":    slug,
        "MODE":    mode,
        "ACCENT":  accent,
        "ACCENT8": accent + conf.get("ACTIVE_ALPHA", "aa"),
        "INACTIVE": inactive,
        "INACTIVE8": inactive + conf.get("INACTIVE_ALPHA", "aa"),
        "KITTY_NAME":     kitty_name,
        "KITTY_UPSTREAM": kitty_upstream,
        "HYPR_HEADER":    hypr_header,
        "NVIM_HEADER":    nvim_header,
        "QT_SCHEME": conf.get("QT_SCHEME", ""),
    })
    return ctx


def render(template: str, ctx: dict[str, str]) -> str:
    out = template
    # Longest keys first so {{ACCENT}} never eats part of {{ACCENT8}}.
    for key in sorted(ctx, key=len, reverse=True):
        out = out.replace("{{%s}}" % key, str(ctx[key]))
    return out


# Which metadata placeholders each template legitimately contains.
# Scoping this per-file removes all ambiguity: NAME, HYPR_HEADER and
# NVIM_HEADER are often the SAME string for the reference theme, so a single
# global substitution pass cannot tell them apart and would pick arbitrarily.
TEMPLATE_META = {
    "kitty-theme.conf.tpl":    ["KITTY_NAME", "KITTY_UPSTREAM"],
    "hyprland-colors.lua.tpl": ["HYPR_HEADER", "SLUG", "ACCENT8", "ACCENT",
                                "INACTIVE8", "INACTIVE"],
    "nvim-colors.lua.tpl":     ["NVIM_HEADER", "SLUG", "MODE"],
    "quickshell-colors.json.tpl": ["MODE"],
}

# Templates whose reference theme differs from the default.
#
# Empty at the moment. It existed for dunstrc, which was the one file not purely
# palette-derived in the reference theme (catppuccin-mocha's dunst config
# contained literals like #cd0373 that appear in no palette), and dunst is gone.
TEMPLATE_REF = {}


def make_templates() -> None:
    """Derive templates from the reference theme(s) by substituting values."""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    default_ctx = build_context(REFERENCE)

    for tpl_name, fname in OUTPUTS.items():
        ref = TEMPLATE_REF.get(tpl_name, REFERENCE)
        ref_dir = os.path.join(THEMES_DIR, ref)
        ctx = default_ctx if ref == REFERENCE else build_context(ref)

        src = os.path.join(ref_dir, fname)
        if not os.path.exists(src):
            print(f"  skip {fname} (reference {ref} has no such file)", file=sys.stderr)
            continue

        txt = open(src).read()

        # Only the metadata keys this template actually uses, so identical
        # values (e.g. NAME == HYPR_HEADER) cannot be mis-assigned.
        subs = []
        for key in TEMPLATE_META.get(tpl_name, []):
            if key in ("MODE",):
                subs.append(('"%s"' % ctx[key], '"{{MODE}}"'))
            elif key.endswith("8"):
                subs.append((ctx[key], "{{%s}}" % key))
            else:
                subs.append((ctx[key], "{{%s}}" % key))
        # SLUG must not clobber a longer metadata value, handled by sorting below.
        for key in PALETTE_KEYS:
            if key in ctx and str(ctx[key]).startswith("#"):
                subs.append((str(ctx[key]), "{{%s}}" % key))

        for value, placeholder in sorted(subs, key=lambda p: -len(p[0])):
            if not value:
                continue
            txt = re.sub(re.escape(value), placeholder, txt, flags=re.I)

        with open(os.path.join(TEMPLATES_DIR, tpl_name), "w") as f:
            f.write(txt)
        print(f"  template {tpl_name} <- {ref}/{fname}")


def generate_theme(theme: str, dest_dir: str | None = None) -> dict[str, str]:
    """Render every output for a theme. Returns {filename: content}."""
    theme_dir = os.path.join(THEMES_DIR, theme)
    ctx = build_context(theme)
    results = {}

    for tpl_name, fname in OUTPUTS.items():
        # 4. overrides/<file> wins outright
        override = os.path.join(theme_dir, "overrides", fname)
        if os.path.exists(override):
            results[fname] = open(override).read()
            continue

        tpl_path = os.path.join(TEMPLATES_DIR, tpl_name)
        if not os.path.exists(tpl_path):
            continue
        results[fname] = render(open(tpl_path).read(), ctx)

    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
        for fname, content in results.items():
            with open(os.path.join(dest_dir, fname), "w") as f:
                f.write(content)

    return results


def render_outputs(ctx: dict[str, str], dest_dir: str, extra: dict[str, str] | None = None) -> None:
    """Render every output (plus `extra` {template: filename}) into dest_dir.
    For themes outside config/themes/: no overrides/ lookup."""
    os.makedirs(dest_dir, exist_ok=True)
    for tpl_name, fname in {**OUTPUTS, **(extra or {})}.items():
        tpl_path = os.path.join(TEMPLATES_DIR, tpl_name)
        if os.path.exists(tpl_path):
            with open(os.path.join(dest_dir, fname), "w") as f:
                f.write(render(open(tpl_path).read(), ctx))


def cmd_check(only: list[str] | None) -> int:
    """Verify generated output matches what is committed."""
    themes = only or theme_dirs()
    identical = differing = missing = 0
    details = []

    for theme in themes:
        results = generate_theme(theme)
        for fname, content in results.items():
            path = os.path.join(THEMES_DIR, theme, fname)
            if not os.path.exists(path):
                missing += 1
                details.append((theme, fname, "MISSING"))
                continue
            if open(path).read() == content:
                identical += 1
            else:
                differing += 1
                details.append((theme, fname, "DIFFERS"))

    total = identical + differing + missing
    print(f"identical: {identical}/{total}")
    if differing:
        print(f"differing: {differing}")
    if missing:
        print(f"missing:   {missing}")
    for theme, fname, status in details[:40]:
        print(f"  {status:8} {theme}/{fname}")
    if len(details) > 40:
        print(f"  ... and {len(details) - 40} more")

    return 0 if not (differing or missing) else 1


def cmd_generate(only: list[str] | None) -> int:
    themes = only or theme_dirs()
    for theme in themes:
        results = generate_theme(theme)
        theme_dir = os.path.join(THEMES_DIR, theme)
        for fname, content in results.items():
            with open(os.path.join(theme_dir, fname), "w") as f:
                f.write(content)
        print(f"generated {theme} ({len(results)} files)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify generated output matches the committed tree")
    ap.add_argument("--templates", action="store_true",
                    help=f"re-derive templates from {REFERENCE}")
    ap.add_argument("--theme", action="append", default=None,
                    help="limit to this theme (repeatable)")
    args = ap.parse_args()

    if args.templates:
        print(f"deriving templates from {REFERENCE}...")
        make_templates()
        return 0

    if args.check:
        return cmd_check(args.theme)
    return cmd_generate(args.theme)


if __name__ == "__main__":
    sys.exit(main())
