from pathlib import Path

import bpy
import _rna_xml as rna_xml

RNA_MAP = (
    ("preferences.themes[0]", "Theme"),
    ("preferences.ui_styles[0]", "ThemeStyle"),
)


def export_theme(dest_path: Path) -> None:
    rna_xml.xml_file_write(bpy.context, str(dest_path), RNA_MAP)


def import_theme(src_path: Path) -> None:
    menu_cls = bpy.types.USERPREF_MT_interface_theme_presets
    secure_types = getattr(menu_cls, "preset_xml_secure_types", None)
    rna_xml.xml_file_run(bpy.context, str(src_path), RNA_MAP, secure_types=secure_types)
