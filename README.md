# MyGitBlender

A Blender add-on (Extension) that syncs your Hotkeys, Theme, Start-Up file, general Preferences, and installed-add-on list to a GitHub repo — so switching computers means one **Pull** instead of re-configuring everything by hand.

Compatible with **Blender 4.2+** (tested on 5.1).

## Features

- **Push / Pull** buttons in `Edit > Preferences > Add-ons` — git runs in the background, no UI freeze
- **Selective sync** — choose which categories to include (Hotkeys, Theme, Add-on List, Start-Up File, Preferences)
- **Status line** — see at a glance when, where, and from which Blender version the last sync happened
- **Conflict protection** — Push refuses if the remote has newer changes; Pull warns before overwriting unpushed local edits
- **Blender version tagging** — warns when pulling a config pushed from a different Blender version
- **Sync history** — browse past syncs and restore any older snapshot
- **Add-on manifest** — `addons.json` + `addons.md` record every installed add-on; missing official extensions can be **reinstalled with one click** on a new machine
- **Push reminder** — optional popup when your config changed but wasn't pushed
- **First-Time Setup** — one dialog on a fresh machine: paste your repo URL, everything gets pulled

## Install

1. Download/zip the `MyGitBlender` folder (must contain `blender_manifest.toml` at its root).
2. In Blender: `Edit > Preferences > Get Extensions` → top-right dropdown → **Install from Disk…** → pick the zip.
3. Enable it. A **MyGitBlender** section appears under `Edit > Preferences > Add-ons`.
4. Requires the `git` CLI installed and authenticated with GitHub (e.g. via GitHub Desktop or `gh auth login`).

## Project structure

| File | Role |
|------|------|
| `__init__.py` | Registration entry point |
| `preferences.py` | Add-on preferences UI (repo URL, sync checkboxes, buttons, status line) |
| `operators.py` | Push/Pull (background-threaded), history browser, snapshot restore, missing-add-on installer, setup wizard |
| `git_wrapper.py` | Subprocess git wrapper (no `bpy` dependency) |
| `config_paths.py` | Resolves Blender's config dir and the local mirror location |
| `sync_keymap.py` / `sync_theme.py` | Keymap/theme export-import via Blender's native text formats |
| `sync_binary.py` | Binary copy of `startup.blend` / `userpref.blend` with hash-based change detection |
| `sync_addons.py` | Installed-add-on manifest (`addons.json` / `addons.md`) and missing-add-on diff |
| `conflict.py` | Remote-diverged and local-unsynced-changes detection |
| `version_tag.py` | Sync metadata (`sync_manifest.json`), commit messages, panel status text |
| `reminder.py` | Periodic unsynced-changes reminder popup |
| `blender_manifest.toml` | Extension metadata |
