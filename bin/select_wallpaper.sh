#!/usr/bin/env bash
# Pick a wallpaper from the active theme's backgrounds/ and cache it for
# hyprpaper/hyprlock to pick up. If the theme ships 2+ backgrounds, the first
# (alphabetically) is used during the day (7 AM-7 PM) and the second at night.

set -euo pipefail

BACKGROUNDS_DIR="$HOME/.config/theme/current/backgrounds"
CACHE_DIR="$HOME/.cache/appearance"
CACHE_FILE="$CACHE_DIR/wallpaper.png"

mapfile -t backgrounds < <(find "$BACKGROUNDS_DIR" -maxdepth 1 -type f | sort)

if [[ ${#backgrounds[@]} -eq 0 ]]; then
  echo "error: no backgrounds found in $BACKGROUNDS_DIR" >&2
  exit 1
fi

if [[ ${#backgrounds[@]} -ge 2 ]]; then
  hour=$(date +%H)
  if [[ $hour -ge 7 && $hour -lt 19 ]]; then
    src="${backgrounds[0]}"
  else
    src="${backgrounds[1]}"
  fi
else
  src="${backgrounds[0]}"
fi

mkdir -p "$CACHE_DIR"
cp -- "$src" "$CACHE_FILE"
