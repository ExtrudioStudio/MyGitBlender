import bpy

from . import config_paths
from . import git_wrapper
from . import sync_addons
from . import sync_keymap
from . import sync_theme


def _get_repo_url(context):
    return context.preferences.addons[__package__].preferences.repo_url.strip()


class MYGITBLENDER_OT_push(bpy.types.Operator):
    bl_idname = "mygitblender.push"
    bl_label = "Push"
    bl_description = "Save current Blender config to the GitHub repo"

    def execute(self, context):
        repo_url = _get_repo_url(context)
        if not repo_url:
            self.report({'ERROR'}, "Set a GitHub Repo URL in the add-on preferences first")
            return {'CANCELLED'}

        mirror_dir = config_paths.get_mirror_dir()
        ok, msg = git_wrapper.ensure_repo(mirror_dir, repo_url)
        if not ok:
            self.report({'ERROR'}, f"Git setup failed: {msg}")
            return {'CANCELLED'}

        sync_keymap.export_keymap(mirror_dir / "keymap.py")
        sync_theme.export_theme(mirror_dir / "theme.xml")
        sync_addons.write_addons_manifest(mirror_dir, sync_addons.collect_installed_addons())

        committed, commit_msg = git_wrapper.commit_all(mirror_dir, "MyGitBlender: sync keymap + theme + addon list")
        if not committed and commit_msg != "nothing to commit":
            self.report({'ERROR'}, f"Commit failed: {commit_msg}")
            return {'CANCELLED'}

        ok, out = git_wrapper.push(mirror_dir)
        if not ok:
            self.report({'ERROR'}, f"Push failed: {out}")
            return {'CANCELLED'}

        if committed:
            self.report({'INFO'}, "Pushed keymap + theme + addon list to GitHub")
        else:
            self.report({'INFO'}, "Already up to date with GitHub")
        return {'FINISHED'}


class MYGITBLENDER_OT_pull(bpy.types.Operator):
    bl_idname = "mygitblender.pull"
    bl_label = "Pull"
    bl_description = "Restore Blender config from the GitHub repo"

    def execute(self, context):
        repo_url = _get_repo_url(context)
        if not repo_url:
            self.report({'ERROR'}, "Set a GitHub Repo URL in the add-on preferences first")
            return {'CANCELLED'}

        mirror_dir = config_paths.get_mirror_dir()
        ok, msg = git_wrapper.ensure_repo(mirror_dir, repo_url)
        if not ok:
            self.report({'ERROR'}, f"Git setup failed: {msg}")
            return {'CANCELLED'}

        ok, out = git_wrapper.pull(mirror_dir)
        if not ok:
            self.report({'ERROR'}, f"Pull failed: {out}")
            return {'CANCELLED'}

        applied = []

        keymap_file = mirror_dir / "keymap.py"
        if keymap_file.exists():
            sync_keymap.import_keymap(keymap_file)
            applied.append("keymap")

        theme_file = mirror_dir / "theme.xml"
        if theme_file.exists():
            sync_theme.import_theme(theme_file)
            applied.append("theme")

        remote_addons = sync_addons.read_addons_manifest(mirror_dir)
        missing = sync_addons.diff_missing_addons(remote_addons) if remote_addons else []

        if applied:
            msg = f"Applied: {', '.join(applied)}"
        else:
            msg = "Nothing to apply yet - push from another machine first"

        if missing:
            names = ", ".join(e["name"] for e in missing[:5])
            more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            msg += f". Missing add-ons: {names}{more} - see addons.md in the mirror"

        self.report({'WARNING'} if missing else {'INFO'}, msg)
        return {'FINISHED'}


classes = (
    MYGITBLENDER_OT_push,
    MYGITBLENDER_OT_pull,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
