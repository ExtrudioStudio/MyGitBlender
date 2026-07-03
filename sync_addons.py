import json
from pathlib import Path

import addon_utils


def collect_installed_addons() -> list[dict]:
    entries = []
    for mod in addon_utils.modules(refresh=True):
        mod_name = mod.__name__
        bl_info = mod.bl_info
        _, enabled = addon_utils.check(mod_name)
        is_extension = addon_utils.check_extension(mod_name)

        repo_id = None
        if is_extension:
            parts = mod_name.split(".")
            if len(parts) >= 2:
                repo_id = parts[1]

        version = bl_info.get("version")
        entries.append({
            "name": bl_info.get("name", mod_name),
            "module": mod_name,
            "version": list(version) if version else None,
            "enabled": bool(enabled),
            "is_extension": is_extension,
            "repo": repo_id,
        })

    entries.sort(key=lambda e: e["name"].lower())
    return entries


def write_addons_manifest(dest_dir: Path, entries: list[dict]) -> None:
    (dest_dir / "addons.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")

    lines = ["# Installed Add-ons", ""]
    for e in entries:
        status = "x" if e["enabled"] else " "
        version = ".".join(str(v) for v in e["version"]) if e["version"] else "?"
        source = f"extension ({e['repo']})" if e["is_extension"] else "legacy add-on"
        lines.append(f"- [{status}] **{e['name']}** `{e['module']}` v{version} — {source}")

    (dest_dir / "addons.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_addons_manifest(dest_dir: Path) -> list[dict]:
    json_path = dest_dir / "addons.json"
    if not json_path.exists():
        return []
    return json.loads(json_path.read_text(encoding="utf-8"))


def diff_missing_addons(remote_entries: list[dict]) -> list[dict]:
    installed = {e["module"]: e for e in collect_installed_addons()}
    missing = []
    for e in remote_entries:
        if not e["enabled"]:
            continue
        local = installed.get(e["module"])
        if local is None or not local["enabled"]:
            missing.append(e)
    return missing
