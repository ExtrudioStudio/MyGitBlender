from pathlib import Path

from . import git_wrapper
from . import sync_keymap
from . import sync_theme


def remote_has_diverged(mirror_dir: Path) -> bool:
    git_wrapper.fetch(mirror_dir)
    return git_wrapper.remote_ahead_count(mirror_dir) > 0


def local_unsynced_categories(mirror_dir: Path, prefs) -> list[str]:
    """Categories where the live Blender config differs from the mirror's
    last-synced copy - i.e. pulling now would silently overwrite them."""
    changed = []

    if prefs.sync_keymap:
        existing = mirror_dir / "keymap.py"
        if existing.exists():
            tmp = mirror_dir / ".tmp_keymap_check.py"
            sync_keymap.export_keymap(tmp)
            differs = tmp.read_bytes() != existing.read_bytes()
            tmp.unlink(missing_ok=True)
            if differs:
                changed.append("keymap")

    if prefs.sync_theme:
        existing = mirror_dir / "theme.xml"
        if existing.exists():
            tmp = mirror_dir / ".tmp_theme_check.xml"
            sync_theme.export_theme(tmp)
            differs = tmp.read_bytes() != existing.read_bytes()
            tmp.unlink(missing_ok=True)
            if differs:
                changed.append("theme")

    return changed
