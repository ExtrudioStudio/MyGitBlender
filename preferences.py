import bpy

from . import config_paths


class MyGitBlenderPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    repo_url: bpy.props.StringProperty(
        name="GitHub Repo URL",
        description="HTTPS or SSH URL of the GitHub repo to sync with",
        default="",
    )

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "repo_url")

        row = layout.row()
        row.label(text=f"Local mirror: {config_paths.get_mirror_dir()}")

        row = layout.row(align=True)
        row.operator("mygitblender.push", icon='EXPORT')
        row.operator("mygitblender.pull", icon='IMPORT')


classes = (
    MyGitBlenderPreferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
