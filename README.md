# dotfiles-theme

Central theming system consumed by `quickshell`, `kitty`, `hypr`, `nvim`, and Qt apps. One directory per theme under `config/themes/<name>/` — Catppuccin flavors plus a set ported from [omarchy](https://github.com/basecamp/omarchy) (MIT licensed), each with a palette, a Qt accent selection, and one or more wallpapers.

Part of the [dotfiles-arch](https://github.com/SaratAngajalaoffl/dotfiles-arch) multi-repo dotfiles system.

## Layout

- `config` → `~/.config/theme` (see `.links`)
- `bin/*` → `~/.local/bin/` — `theme-set.sh`, `select_wallpaper.sh`, `wallpaper.py`
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

## Wallpapers

Every wallpaper is a theme: picking one applies a colour scheme with it.

- A theme's own `backgrounds/` image applies that theme's curated palette.
- Anything in `config/wallpapers/` gets a palette generated from the image
  (matugen, with Catppuccin's terminal hues leaned towards the wallpaper's
  colour), rendered through the same templates into
  `~/.local/state/theme/generated/<slug>/` and cached until the image changes.
  An entry can name a curated palette instead with `"theme"`.

`config/wallpapers.json` holds each wallpaper's display name and tags, keyed by
its path under `config/`. `light`/`dark` tags come from the palette's mode
automatically. The shell's Themes widget (`SUPER+T`) browses,
searches, tags and applies them; the CLI does the same:

```bash
wallpaper.py import ~/Downloads/*.jpg --tags anime,cityscape   # add (dupes skipped)
wallpaper.py tag wallpapers/tokyo-rain.jpg anime,cityscape,night
wallpaper.py apply wallpapers/tokyo-rain.jpg
wallpaper.py list                                              # JSON, for the shell
```

Applying goes through `theme-set.sh` with `WALLPAPER=` set, so kitty (reloaded
with `SIGUSR1`), Hyprland, Qt and the shell all recolour live. The choice is
remembered in `~/.local/state/theme/wallpaper.json` and restored at login;
`theme-set.sh <name>` on its own clears it and uses the theme's background.

## Usage

```bash
theme-set.sh <theme-name>   # switch theme, set wallpaper, reload the shell and Hyprland
python3 bin/theme-gen.py --check   # verify generated files match the tree
```

In the shell, `SUPER+T` opens the Themes widget — the wallpaper library above, which drives the same `theme-set.sh`.

`~/.config/theme/current` symlinks to the active theme directory. Adding a new theme means copying an existing `config/themes/<name>/` directory, editing `palette.json`/`theme.conf`, and dropping in wallpaper(s).

## Setup

Bootstrapped to the default theme (`catppuccin-mocha`) on a fresh install by the parent repo's `install.sh`, without overriding one you've already chosen.
