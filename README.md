# dotfiles-theme

Central theming system consumed by `waybar`, `kitty`, `rofi`, `dunst`, `hypr`, `nvim`, and Qt apps. One directory per theme under `config/themes/<name>/` — Catppuccin flavors plus a set ported from [omarchy](https://github.com/basecamp/omarchy) (MIT licensed), each with a full set of per-app themed files, a Qt accent selection, and one or more wallpapers.

Part of the [dotfiles-arch](https://github.com/SaratAngajalaoffl/dotfiles-arch) multi-repo dotfiles system.

## Layout

- `config` → `~/.config/theme` (see `.links`)
- `bin/*` → `~/.local/bin/` — `theme-set.sh` and `theme-menu.sh`
- `config/themes/<name>/theme.conf`, `waybar-colors.css`, `kitty-theme.conf`, `rofi-colors.rasi`, `dunstrc`, `hyprland-colors.lua`, `nvim-colors.lua`, `backgrounds/`

## Usage

```bash
theme-set.sh <theme-name>   # switch theme, reload waybar/dunst, set wallpaper, reload Hyprland
theme-menu.sh                # rofi picker, bound to SUPER+CTRL+SPACE
```

`~/.config/theme/current` symlinks to the active theme directory. Adding a new theme means copying an existing `config/themes/<name>/` directory, editing the per-app files, and dropping in wallpaper(s).

## Setup

Bootstrapped to the default theme (`catppuccin-mocha`) on a fresh install by the parent repo's `install.sh`, without overriding one you've already chosen.
