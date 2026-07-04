import bpy

from . import config_paths
from . import conflict

_CHECK_INTERVAL = 1800.0  # seconds between checks
_FIRST_CHECK = 600.0      # let Blender settle before the first one
_reminded = False         # only nag once per session


def _get_prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def _timer():
    global _reminded
    try:
        prefs = _get_prefs()
        if prefs is None or not prefs.remind_unsynced or _reminded:
            return _CHECK_INTERVAL

        from . import operators
        if operators.is_busy():
            return _CHECK_INTERVAL

        mirror_dir = config_paths.get_mirror_dir()
        if not (mirror_dir / ".git").exists():
            return _CHECK_INTERVAL

        unsynced = conflict.local_unsynced_categories(mirror_dir, prefs)
        if unsynced:
            _reminded = True
            _show_popup(unsynced)
    except Exception:
        # A reminder must never break the session; stay silent and retry later.
        pass
    return _CHECK_INTERVAL


def _show_popup(unsynced):
    wm = bpy.context.window_manager
    if not wm or not wm.windows:
        return

    message = f"Unsynced config changes: {', '.join(unsynced)}"

    def draw(menu, _context):
        col = menu.layout.column()
        col.label(text=message)
        col.operator("mygitblender.push", text="Push Now", icon='EXPORT')

    wm.popup_menu(draw, title="MyGitBlender", icon='INFO')


def register():
    bpy.app.timers.register(_timer, first_interval=_FIRST_CHECK, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
