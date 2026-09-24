#!/usr/bin/env bash
# Apply a theme: point every themed app config at the chosen theme's files,
# switch the wallpaper, and reload the running apps that support it.
#
# Usage: theme-set.sh <theme-name | theme-dir>
# Theme names are the directory names under ~/.config/theme/themes/. A path to
# a theme directory also works — that is how wallpaper.py applies the palettes
# it generates (~/.local/state/theme/generated/<slug>/).
#
# Env:
#   WALLPAPER=<image>  put this image up instead of the theme's own background
#                      (wallpaper.py sets it; its choice is remembered in
#                      ~/.local/state/theme/wallpaper.json)
#   THEME_QUIET=1      no "switched theme" notification (the shell's picker)

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

if [[ "$name" == /* ]]; then
  THEME_ROOT="$name"
else
  THEME_ROOT="$THEMES_DIR/$name"
fi
if [[ ! -d "$THEME_ROOT" ]]; then
  echo "error: unknown theme '$name' (looked in $THEMES_DIR)" >&2
  exit 1
fi

ln -sfn "$THEME_ROOT" "$CURRENT_LINK"

# Per-app themed files.
#
# waybar / rofi / dunst / eww are gone (Quickshell replaced them), so their
# symlinks are no longer created — pointing at a config dir that no longer
# exists would just leave dangling links behind. Their generator outputs
# (waybar-colors.css, rofi-colors.rasi, dunstrc, eww-colors.scss) are likewise
# no longer produced; see theme-gen.py OUTPUTS.
ln -sfn "$THEME_ROOT/kitty-theme.conf"    "$HOME/.config/kitty/current-theme.conf"
mkdir -p "$HOME/.config/hypr/conf/hyprland"
ln -sfn "$THEME_ROOT/hyprland-colors.lua" "$HOME/.config/hypr/conf/hyprland/colors.lua"
mkdir -p "$HOME/.config/nvim/lua/config"
ln -sfn "$THEME_ROOT/nvim-colors.lua" "$HOME/.config/nvim/lua/config/theme-colors.lua"

# Qt accent — swap the color_scheme_path line, matching whatever accent this theme declares
if [[ -f "$THEME_ROOT/theme.conf" ]]; then
  # shellcheck disable=SC1090
  source "$THEME_ROOT/theme.conf"
fi
# Generated themes carry their own scheme file (QT_SCHEME_PATH); curated ones
# name one of the committed files in qt5ct/qt6ct's colors/.
for tool in qt5ct qt6ct; do
  cfg="$HOME/.config/$tool/$tool.conf"
  [[ -f "$cfg" ]] || continue
  if [[ -n "${QT_SCHEME_PATH:-}" ]]; then
    scheme="$QT_SCHEME_PATH"
  elif [[ -n "${QT_SCHEME:-}" ]]; then
    scheme="$HOME/.config/$tool/colors/${QT_SCHEME}.conf"
  else
    continue
  fi
  sed -i "s|^color_scheme_path=.*|color_scheme_path=$scheme|" "$cfg"
done

# Wallpaper: the one asked for, else the theme's own (day/night aware if it
# ships 2+ backgrounds).
if [[ -n "${WALLPAPER:-}" ]]; then
  WALLPAPER="$WALLPAPER" "$HOME/.local/bin/select_wallpaper.sh"
else
  # A plain theme switch: the theme's own background takes over, so forget
  # the wallpaper picked earlier (it would come back at the next login).
  rm -f "$HOME/.local/state/theme/wallpaper.json"
  "$HOME/.local/bin/select_wallpaper.sh" --from-theme
fi

# Reload running apps that support it
if [[ -z "${THEME_QUIET:-}" ]] && command -v notify-send >/dev/null 2>&1; then
  notify-send "Theme" "Switched to ${THEME_NAME:-$name}"
fi

# kitty re-reads kitty.conf on SIGUSR1, and with it current-theme.conf (the
# symlink repointed above), so open terminals recolour in place.
pkill -USR1 -x kitty 2>/dev/null || true

# Quickshell picks the palette up on its own: it watches
# ~/.config/theme/current/quickshell-colors.json, and `current` is the symlink
# repointed above, so no per-app symlink is needed for it. It just needs
# nudging to repaint.
if pgrep -x qs >/dev/null 2>&1; then
  qs ipc call theme reload >/dev/null 2>&1 || true
fi

[[ -x "$HOME/.local/bin/reload_all_services.sh" ]] && "$HOME/.local/bin/reload_all_services.sh" || true
command -v hyprctl >/dev/null 2>&1 && hyprctl reload >/dev/null 2>&1 || true

echo "theme set to $name"
