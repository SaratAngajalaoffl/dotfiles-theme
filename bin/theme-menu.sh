#!/usr/bin/env bash
# Rofi picker for switching themes. Bound to a keybind in hypr/config/conf/hyprland/keybinds.lua.

set -euo pipefail

THEMES_DIR="$HOME/.config/theme/themes"

mapfile -t names < <(find "$THEMES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

choice=$(printf '%s\n' "${names[@]}" | rofi -dmenu -p "Theme" -i)
[[ -n "$choice" ]] || exit 0

"$HOME/.local/bin/theme-set.sh" "$choice"
