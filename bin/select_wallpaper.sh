#!/usr/bin/env bash
# Put a wallpaper on screen via awww and cache it for hyprlock.
#
# Which one, in order:
#   1. $WALLPAPER, when set (theme-set.sh passes the one picked in the shell)
#   2. the last one picked (~/.local/state/theme/wallpaper.json, written by
#      wallpaper.py) — so a login keeps your choice; skipped with --from-theme
#   3. the active theme's backgrounds/: with 2+, the first (alphabetically) is
#      used during the day (7 AM-7 PM) and the second at night.

set -euo pipefail

BACKGROUNDS_DIR="$HOME/.config/theme/current/backgrounds"
CHOSEN="$HOME/.local/state/theme/wallpaper.json"
CACHE_DIR="$HOME/.cache/appearance"
CACHE_FILE="$CACHE_DIR/wallpaper.png"

src="${WALLPAPER:-}"
if [[ -z "$src" && "${1:-}" != "--from-theme" && -f "$CHOSEN" ]]; then
  src=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("path", ""))' "$CHOSEN" 2>/dev/null || true)
  [[ -f "$src" ]] || src=""
fi

# -L: a generated theme's backgrounds/ holds a symlink to the library image.
mapfile -t backgrounds < <(find -L "$BACKGROUNDS_DIR" -maxdepth 1 -type f | sort)

if [[ -z "$src" ]]; then
  if [[ ${#backgrounds[@]} -eq 0 ]]; then
    # A theme can have no wallpaper of its own (its image was dropped from
    # the library); keep whatever is on screen.
    echo "no backgrounds in $BACKGROUNDS_DIR, keeping the current wallpaper" >&2
    exit 0
  elif [[ ${#backgrounds[@]} -ge 2 ]]; then
    hour=$(date +%H)
    if [[ $hour -ge 7 && $hour -lt 19 ]]; then
      src="${backgrounds[0]}"
    else
      src="${backgrounds[1]}"
    fi
  else
    src="${backgrounds[0]}"
  fi
fi

mkdir -p "$CACHE_DIR"
cp -- "$src" "$CACHE_FILE"

# hyprpaper used to watch $CACHE_FILE and follow along on its own. awww does
# not watch anything — it needs an explicit `img` call, so a theme switch has to
# push the image itself or the desktop keeps the previous theme's wallpaper.
#
# The daemon is started at login (see hypr autostart); starting it here too
# would race with that, so bail out quietly if it is not up yet.
if pgrep -x awww-daemon >/dev/null 2>&1; then
  awww img "$CACHE_FILE" --transition-type grow --transition-duration 1 --transition-fps 60
fi
