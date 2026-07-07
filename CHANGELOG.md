# Changelog

## 0.3.2

- Added the LICENSE file (GPL-2.0-or-later, matching the manifest).
- Added this changelog.
- Friendlier error when pulling from a repo that has no commits yet.
- Code cleanup pass: removed unused functions and a few internal rough edges
  found in a full review. No behavior changes beyond the error message above.

## 0.3.1

- New Install Git button in the Setup Health Check, shown when git isn't
  found. Uses winget on Windows or the developer tools installer on macOS,
  and falls back to opening the download page elsewhere.

## 0.3.0

- Setup Health Check: verifies git, your identity, the repo URL, and repo
  access, each with fix-it guidance.
- Set Git Identity dialog. Applies only to the add-on's own repo, never
  your global git settings.
- Plain language error messages for the common git failures. Git can no
  longer freeze Blender waiting for a password.
- Automatic local backup before every Pull or snapshot restore, with an
  Undo Last Pull button. The last 10 backups are kept.

## 0.2.1

- Pull now asks before reinstalling missing add-ons, with a popup listing
  what's missing and an Install All button.

## 0.2.0

- Status line showing when, where, and from which Blender version the
  last sync happened.
- Push and Pull run in the background. No more UI freeze during git.
- Optional reminder popup when your config has unsynced changes.
- One-click reinstall of missing add-ons that came from an online
  extensions repository.

## 0.1.0

- First working version: Push/Pull of hotkeys, theme, start-up file,
  preferences, and the installed add-on list to a GitHub repo.
- Selective sync checkboxes, conflict detection, Blender version tagging,
  sync history browser with snapshot restore, and a first-time setup
  wizard for new machines.
