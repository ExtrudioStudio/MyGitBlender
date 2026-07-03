import hashlib
import shutil
from pathlib import Path

from . import config_paths

STARTUP_FILENAME = "startup.blend"
USERPREF_FILENAME = "userpref.blend"


def _hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _export(dest_dir: Path, filename: str) -> bool:
    src = config_paths.get_blender_config_dir() / filename
    if not src.exists():
        return False
    shutil.copy2(src, dest_dir / filename)
    return True


def _import(mirror_dir: Path, filename: str) -> bool:
    src = mirror_dir / filename
    if not src.exists():
        return False
    dest_dir = config_paths.get_blender_config_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / filename)
    return True


def export_startup(dest_dir: Path) -> bool:
    return _export(dest_dir, STARTUP_FILENAME)


def export_preferences(dest_dir: Path) -> bool:
    return _export(dest_dir, USERPREF_FILENAME)


def import_startup(mirror_dir: Path) -> bool:
    return _import(mirror_dir, STARTUP_FILENAME)


def import_preferences(mirror_dir: Path) -> bool:
    return _import(mirror_dir, USERPREF_FILENAME)


def has_changed(mirror_dir: Path, filename: str) -> bool:
    live = config_paths.get_blender_config_dir() / filename
    synced = mirror_dir / filename
    return _hash(live) != _hash(synced)
