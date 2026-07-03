# MyGitBlender

A Blender add-on (Extension) that syncs your Hotkeys, Theme, Start-Up file, general Preferences, and installed-add-on list to a GitHub repo — so switching computers means one **Pull** instead of re-configuring everything by hand.

Compatible with **Blender 4.2+** (tested on 5.1).

## Status

Under staged development. Stage 0 (add-on skeleton + Preferences panel shell) is in place; Push/Pull are placeholders until Stage 1.

## Install

1. Download/zip the `MyGitBlender` folder (must contain `blender_manifest.toml` at its root).
2. In Blender: `Edit > Preferences > Get Extensions` → top-right dropdown → **Install from Disk…** → pick the zip.
3. Enable it. A **MyGitBlender** section appears under `Edit > Preferences > Add-ons`.

## Project structure

| File | Role |
|------|------|
| `__init__.py` | Registration entry point |
| `preferences.py` | Add-on preferences UI (repo URL, Push/Pull buttons) |
| `blender_manifest.toml` | Extension metadata |
