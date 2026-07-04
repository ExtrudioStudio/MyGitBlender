import bpy

from . import backup
from . import config_paths
from . import operators
from . import version_tag


class MyGitBlenderPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    repo_url: bpy.props.StringProperty(
        name="GitHub Repo URL",
        description="HTTPS or SSH URL of the GitHub repo to sync with",
        default="",
    )

    sync_keymap: bpy.props.BoolProperty(name="Hotkeys (Keymap)", default=True)
    sync_theme: bpy.props.BoolProperty(name="Theme", default=True)
    sync_addons: bpy.props.BoolProperty(name="Installed Add-on List", default=True)
    sync_startup: bpy.props.BoolProperty(name="Start-Up File", default=False)
    sync_preferences: bpy.props.BoolProperty(name="General Preferences", default=False)

    remind_unsynced: bpy.props.BoolProperty(
        name="Remind me about unsynced changes",
        description="Show a reminder popup when your config has changed but hasn't been pushed",
        default=True,
    )

    # Git author identity, applied mirror-locally (never global). Set via
    # the Set Git Identity dialog in the Setup Health Check.
    git_user_name: bpy.props.StringProperty(default="", options={'HIDDEN'})
    git_user_email: bpy.props.StringProperty(default="", options={'HIDDEN'})

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "repo_url")

        status = version_tag.get_status_text()
        row = layout.row()
        row.label(text=status or "No syncs yet - Push to get started", icon='INFO')

        row = layout.row()
        row.label(text=f"Local mirror: {config_paths.get_mirror_dir()}")

        box = layout.box()
        box.label(text="What to sync:")
        box.prop(self, "sync_keymap")
        box.prop(self, "sync_theme")
        box.prop(self, "sync_addons")
        box.prop(self, "sync_startup", text="Start-Up File (needs restart to apply)")
        box.prop(self, "sync_preferences", text="General Preferences (needs restart to apply)")

        layout.prop(self, "remind_unsynced")

        row = layout.row(align=True)
        row.operator("mygitblender.push", icon='EXPORT')
        row.operator("mygitblender.pull", icon='IMPORT')
        row.operator("mygitblender.browse_history", icon='RECOVER_LAST')

        missing = operators.get_cached_installable_missing()
        if missing:
            layout.operator(
                "mygitblender.install_missing",
                text=f"Install {len(missing)} Missing Add-on(s)",
                icon='IMPORT',
            )

        latest = backup.latest_backup()
        if latest is not None:
            _, info = latest
            taken = info.get("taken_at", "")[:16].replace("T", " ")
            layout.operator(
                "mygitblender.undo_pull",
                text=f"Undo Last Pull (backup from {taken} UTC)",
                icon='LOOP_BACK',
            )

        row = layout.row(align=True)
        row.operator("mygitblender.health_check", icon='CHECKMARK')
        row.operator("mygitblender.first_time_setup", icon='IMPORT')


classes = (
    MyGitBlenderPreferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
