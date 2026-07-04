import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import bpy

from . import config_paths
from . import sync_binary
from . import sync_keymap
from . import sync_theme

_KEEP = 10

# Keyed on the backups root mtime so the panel can call latest_backup()
# every redraw without hitting the filesystem hard.
_cache = {"mtime": None, "value": None}


def get_backup_root() -> Path:
    return config_paths.get_mirror_dir().parent / "backups"


def make_backup(prefs) -> Path:
    """Snapshot the CURRENT live config (per the enabled categories) so a
    Pull or snapshot-restore can be undone."""
    root = get_backup_root()
    root.mkdir(parents=True, exist_ok=True)

    dest = root / datetime.now().strftime("%Y%m%d-%H%M%S")
    dest.mkdir(exist_ok=True)

    categories = []
    if prefs.sync_keymap:
        sync_keymap.export_keymap(dest / "keymap.py")
        categories.append("keymap")
    if prefs.sync_theme:
        sync_theme.export_theme(dest / "theme.xml")
        categories.append("theme")
    if prefs.sync_startup and sync_binary.export_startup(dest):
        categories.append("startup file")
    if prefs.sync_preferences and sync_binary.export_preferences(dest):
        categories.append("preferences")

    (dest / "backup.json").write_text(json.dumps({
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories,
        "blender_version_string": bpy.app.version_string,
    }, indent=2), encoding="utf-8")

    _prune(root)
    return dest


def _prune(root: Path) -> None:
    dirs = sorted(d for d in root.iterdir() if d.is_dir())
    for stale in dirs[:-_KEEP]:
        shutil.rmtree(stale, ignore_errors=True)


def latest_backup():
    """(backup_dir, info_dict) of the newest backup, or None."""
    root = get_backup_root()
    try:
        mtime = root.stat().st_mtime
    except OSError:
        return None

    if _cache["mtime"] != mtime:
        dirs = sorted(d for d in root.iterdir()
                      if d.is_dir() and (d / "backup.json").exists())
        value = None
        if dirs:
            newest = dirs[-1]
            try:
                info = json.loads((newest / "backup.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                info = {}
            value = (newest, info)
        _cache["mtime"] = mtime
        _cache["value"] = value

    return _cache["value"]


def restore(backup_dir: Path) -> tuple[list, list]:
    """Re-apply everything present in a backup. Returns (applied, restart_needed)."""
    applied = []
    restart_needed = []

    keymap_file = backup_dir / "keymap.py"
    if keymap_file.exists():
        sync_keymap.import_keymap(keymap_file)
        applied.append("keymap")

    theme_file = backup_dir / "theme.xml"
    if theme_file.exists():
        sync_theme.import_theme(theme_file)
        applied.append("theme")

    if sync_binary.import_startup(backup_dir):
        applied.append("startup file")
        restart_needed.append("startup file")
    if sync_binary.import_preferences(backup_dir):
        applied.append("preferences")
        restart_needed.append("preferences")

    return applied, restart_needed
