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
