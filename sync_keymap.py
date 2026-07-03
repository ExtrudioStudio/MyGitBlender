from pathlib import Path

import bpy


def export_keymap(dest_path: Path) -> None:
    bpy.ops.preferences.keyconfig_export(filepath=str(dest_path), all=True)


def import_keymap(src_path: Path) -> None:
    bpy.ops.preferences.keyconfig_import(filepath=str(src_path), keep_original=False)
