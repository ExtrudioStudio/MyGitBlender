import bpy

from . import config_paths


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

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "repo_url")

        row = layout.row()
        row.label(text=f"Local mirror: {config_paths.get_mirror_dir()}")

        box = layout.box()
        box.label(text="What to sync:")
        box.prop(self, "sync_keymap")
        box.prop(self, "sync_theme")
        box.prop(self, "sync_addons")

        coming_later = box.column()
        coming_later.enabled = False
        coming_later.prop(self, "sync_startup", text="Start-Up File (coming in a later stage)")
        coming_later.prop(self, "sync_preferences", text="General Preferences (coming in a later stage)")

        row = layout.row(align=True)
        row.operator("mygitblender.push", icon='EXPORT')
        row.operator("mygitblender.pull", icon='IMPORT')
        row.operator("mygitblender.browse_history", icon='RECOVER_LAST')


classes = (
    MyGitBlenderPreferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
