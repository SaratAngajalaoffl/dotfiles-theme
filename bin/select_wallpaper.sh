#!/usr/bin/env bash
# Pick a wallpaper from the active theme's backgrounds/, cache it for hyprlock,
# and put it on screen via awww. If the theme ships 2+ backgrounds, the first
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

# hyprpaper used to watch $CACHE_FILE and follow along on its own. awww does
# not watch anything — it needs an explicit `img` call, so a theme switch has to
# push the image itself or the desktop keeps the previous theme's wallpaper.
#
# The daemon is started at login (see hypr autostart); starting it here too
# would race with that, so bail out quietly if it is not up yet.
if pgrep -x awww-daemon >/dev/null 2>&1; then
  awww img "$CACHE_FILE" --transition-type grow --transition-duration 1 --transition-fps 60
fi
