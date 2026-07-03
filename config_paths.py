import os
import platform
from pathlib import Path

import bpy


def get_blender_config_dir() -> Path:
    return Path(bpy.utils.resource_path('USER')) / "config"


def get_mirror_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ["APPDATA"])
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "MyGitBlender" / "repo"
