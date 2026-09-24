# dotfiles-theme

Central theming system consumed by `quickshell`, `kitty`, `hypr`, `nvim`, and Qt apps. One directory per theme under `config/themes/<name>/` — Catppuccin flavors plus a set ported from [omarchy](https://github.com/basecamp/omarchy) (MIT licensed), each with a palette, a Qt accent selection, and one or more wallpapers.

Part of the [dotfiles-arch](https://github.com/SaratAngajalaoffl/dotfiles-arch) multi-repo dotfiles system.

## Layout

- `config` → `~/.config/theme` (see `.links`)
- `bin/*` → `~/.local/bin/` — `theme-set.sh` and `select_wallpaper.sh`
- `bin/theme-gen.py` — regenerates every theme's per-app files from its `palette.json`
- `templates/` — the `.tpl` skeletons `theme-gen.py` fills in

Each `config/themes/<name>/` holds:

| File                  | Consumed by                              |
| --------------------- | ---------------------------------------- |
| `palette.json`        | **source of truth** — 26 Catppuccin-named colours |
| `theme.conf`          | `theme-set.sh` (name, mode, Qt accent, border colours) |
| `kitty-theme.conf`    | kitty (`current-theme.conf`)             |
| `hyprland-colors.lua` | Hyprland (`colors.lua`)                  |
| `nvim-colors.lua`     | Neovim (`theme-colors.lua`)              |
| `quickshell-colors.json` | Quickshell (read via `theme/current`) |
| `backgrounds/`        | wallpapers, committed to the repo        |

Everything except `palette.json`, `theme.conf` and `backgrounds/` is **generated** — edit the palette or the templates, not the output. `theme-gen.py --check` verifies the committed tree still matches what the generator produces.

Where a theme needs to deviate from pure palette substitution, `overrides/` is the escape hatch: `overrides/palette.json` is merged onto the palette, and an `overrides/<file>` is used verbatim instead of the rendered output.

## Usage

```bash
theme-set.sh <theme-name>   # switch theme, set wallpaper, reload the shell and Hyprland
python3 bin/theme-gen.py --check   # verify generated files match the tree
```

In the shell, `SUPER+CTRL+SPACE` opens the theme picker (it drives the same `theme-set.sh`).

`~/.config/theme/current` symlinks to the active theme directory. Adding a new theme means copying an existing `config/themes/<name>/` directory, editing `palette.json`/`theme.conf`, and dropping in wallpaper(s).

## Setup

Bootstrapped to the default theme (`catppuccin-mocha`) on a fresh install by the parent repo's `install.sh`, without overriding one you've already chosen.
