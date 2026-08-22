#!/usr/bin/env bash
# Apply a theme: point every themed app config at the chosen theme's files,
# switch the wallpaper, and reload the running apps that support it.
#
# Usage: theme-set.sh <theme-name>
# Theme names are the directory names under ~/.config/theme/themes/.

set -euo pipefail

THEMES_DIR="$HOME/.config/theme/themes"
CURRENT_LINK="$HOME/.config/theme/current"

name="${1:-}"
if [[ -z "$name" ]]; then
  echo "usage: theme-set.sh <theme-name>" >&2
  echo "available themes:" >&2
  find "$THEMES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n' 2>/dev/null | sort >&2
  exit 1
fi

THEME_ROOT="$THEMES_DIR/$name"
if [[ ! -d "$THEME_ROOT" ]]; then
  echo "error: unknown theme '$name' (looked in $THEMES_DIR)" >&2
  exit 1
fi

ln -sfn "$THEME_ROOT" "$CURRENT_LINK"

# Per-app themed files
ln -sfn "$THEME_ROOT/waybar-colors.css"   "$HOME/.config/waybar/colors.css"
ln -sfn "$THEME_ROOT/kitty-theme.conf"    "$HOME/.config/kitty/current-theme.conf"
ln -sfn "$THEME_ROOT/rofi-colors.rasi"    "$HOME/.config/rofi/colors.rasi"
ln -sfn "$THEME_ROOT/dunstrc"             "$HOME/.config/dunst/dunstrc"
mkdir -p "$HOME/.config/hypr/conf/hyprland"
ln -sfn "$THEME_ROOT/hyprland-colors.lua" "$HOME/.config/hypr/conf/hyprland/colors.lua"

# Qt accent — swap the color_scheme_path line, matching whatever accent this theme declares
if [[ -f "$THEME_ROOT/theme.conf" ]]; then
  # shellcheck disable=SC1090
  source "$THEME_ROOT/theme.conf"
fi
if [[ -n "${QT_SCHEME:-}" ]]; then
  for tool in qt5ct qt6ct; do
    cfg="$HOME/.config/$tool/$tool.conf"
    [[ -f "$cfg" ]] || continue
    sed -i "s|^color_scheme_path=.*|color_scheme_path=$HOME/.config/$tool/colors/${QT_SCHEME}.conf|" "$cfg"
  done
fi

# Wallpaper (day/night aware if the theme ships 2+ backgrounds)
"$HOME/.local/bin/select_wallpaper.sh"

# Reload running apps that support it
command -v notify-send >/dev/null 2>&1 && notify-send "Theme" "Switched to ${THEME_NAME:-$name}"
[[ -x "$HOME/.local/bin/reload_all_services.sh" ]] && "$HOME/.local/bin/reload_all_services.sh" || true
command -v hyprctl >/dev/null 2>&1 && hyprctl reload >/dev/null 2>&1 || true

echo "theme set to $name"
