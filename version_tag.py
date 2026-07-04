import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import bpy

MANIFEST_FILENAME = "sync_manifest.json"


def write_version_tag(dest_dir: Path) -> None:
    data = {
        "blender_version": list(bpy.app.version),
        "blender_version_string": bpy.app.version_string,
        "pushed_at": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
    }
    (dest_dir / MANIFEST_FILENAME).write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_version_tag(dest_dir: Path) -> dict | None:
    path = dest_dir / MANIFEST_FILENAME
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def version_mismatch(dest_dir: Path) -> dict | None:
    tag = read_version_tag(dest_dir)
    return _check(tag)


def version_mismatch_from_text(manifest_text: str) -> dict | None:
    if not manifest_text:
        return None
    try:
        tag = json.loads(manifest_text)
    except json.JSONDecodeError:
        return None
    return _check(tag)


def _check(tag: dict | None) -> dict | None:
    if tag is None:
        return None
    if tag.get("blender_version") == list(bpy.app.version):
        return None
    return tag


def build_commit_message(changed: list[str]) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    hostname = platform.node()
    return f"{timestamp} - {hostname} - Blender {bpy.app.version_string} - sync {', '.join(changed)}"


# Cached parse of the manifest so the preferences panel can show a status
# line on every redraw without re-reading/re-parsing the file each time.
_status_cache = {"mtime": None, "tag": None}


def get_status_text() -> str | None:
    from . import config_paths

    path = config_paths.get_mirror_dir() / MANIFEST_FILENAME
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    if _status_cache["mtime"] != mtime:
        try:
            _status_cache["tag"] = json.loads(path.read_text(encoding="utf-8"))
            _status_cache["mtime"] = mtime
        except (OSError, json.JSONDecodeError):
            return None

    tag = _status_cache["tag"]
    try:
        pushed = datetime.fromisoformat(tag["pushed_at"])
    except (KeyError, ValueError):
        return None

    hostname = tag.get("hostname", "?")
    if hostname == platform.node():
        hostname = "this machine"

    ago = _format_ago(datetime.now(timezone.utc) - pushed)
    return f"Last sync: {ago} · {hostname} · Blender {tag.get('blender_version_string', '?')}"


def _format_ago(delta) -> str:
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"
