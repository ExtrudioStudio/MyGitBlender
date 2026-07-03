import bpy

from . import config_paths
from . import conflict
from . import git_wrapper
from . import sync_addons
from . import sync_keymap
from . import sync_theme
from . import version_tag


def _get_prefs(context):
    return context.preferences.addons[__package__].preferences


class MYGITBLENDER_OT_push(bpy.types.Operator):
    bl_idname = "mygitblender.push"
    bl_label = "Push"
    bl_description = "Save current Blender config to the GitHub repo"

    def execute(self, context):
        prefs = _get_prefs(context)
        repo_url = prefs.repo_url.strip()
        if not repo_url:
            self.report({'ERROR'}, "Set a GitHub Repo URL in the add-on preferences first")
            return {'CANCELLED'}

        mirror_dir = config_paths.get_mirror_dir()
        ok, msg = git_wrapper.ensure_repo(mirror_dir, repo_url)
        if not ok:
            self.report({'ERROR'}, f"Git setup failed: {msg}")
            return {'CANCELLED'}

        if conflict.remote_has_diverged(mirror_dir):
            self.report({'ERROR'}, "Remote has changes you haven't pulled yet - Pull first, then Push")
            return {'CANCELLED'}

        changed = []
        if prefs.sync_keymap:
            sync_keymap.export_keymap(mirror_dir / "keymap.py")
            changed.append("keymap")
        if prefs.sync_theme:
            sync_theme.export_theme(mirror_dir / "theme.xml")
            changed.append("theme")
        if prefs.sync_addons:
            sync_addons.write_addons_manifest(mirror_dir, sync_addons.collect_installed_addons())
            changed.append("addon list")

        if not changed:
            self.report({'WARNING'}, "Nothing selected to sync - check a category first")
            return {'CANCELLED'}

        version_tag.write_version_tag(mirror_dir)

        commit_msg = version_tag.build_commit_message(changed)
        committed, commit_result = git_wrapper.commit_all(mirror_dir, commit_msg)
        if not committed and commit_result != "nothing to commit":
            self.report({'ERROR'}, f"Commit failed: {commit_result}")
            return {'CANCELLED'}

        ok, out = git_wrapper.push(mirror_dir)
        if not ok:
            self.report({'ERROR'}, f"Push failed: {out}")
            return {'CANCELLED'}

        if committed:
            self.report({'INFO'}, f"Pushed {', '.join(changed)} to GitHub")
        else:
            self.report({'INFO'}, "Already up to date with GitHub")
        return {'FINISHED'}


class MYGITBLENDER_OT_pull(bpy.types.Operator):
    bl_idname = "mygitblender.pull"
    bl_label = "Pull"
    bl_description = "Restore Blender config from the GitHub repo"

    def invoke(self, context, event):
        prefs = _get_prefs(context)
        repo_url = prefs.repo_url.strip()
        if not repo_url:
            self.report({'ERROR'}, "Set a GitHub Repo URL in the add-on preferences first")
            return {'CANCELLED'}

        mirror_dir = config_paths.get_mirror_dir()
        ok, msg = git_wrapper.ensure_repo(mirror_dir, repo_url)
        if not ok:
            self.report({'ERROR'}, f"Git setup failed: {msg}")
            return {'CANCELLED'}

        # Peek at what pulling would bring in, without touching the working
        # tree yet, so we can warn about both kinds of conflict in one dialog.
        git_wrapper.fetch(mirror_dir)

        warnings = []

        unsynced = conflict.local_unsynced_categories(mirror_dir, prefs)
        if unsynced:
            warnings.append(f"You have unpushed local changes to: {', '.join(unsynced)}.")

        remote_manifest = git_wrapper.show_file_at_ref(mirror_dir, "@{u}", version_tag.MANIFEST_FILENAME)
        tag = version_tag.version_mismatch_from_text(remote_manifest) if remote_manifest else None
        if tag:
            remote_ver = tag.get("blender_version_string", "unknown")
            hostname = tag.get("hostname", "another machine")
            warnings.append(
                f"This config was pushed from Blender {remote_ver} on '{hostname}', "
                f"you're running {bpy.app.version_string}."
            )

        if warnings:
            message = " ".join(warnings) + " Pulling now may overwrite or not apply cleanly. Continue?"
            return context.window_manager.invoke_confirm(
                self, event, title="Heads up before pulling", message=message, confirm_text="Pull anyway",
            )

        return self.execute(context)

    def execute(self, context):
        prefs = _get_prefs(context)
        repo_url = prefs.repo_url.strip()
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
        missing = []

        keymap_file = mirror_dir / "keymap.py"
        if prefs.sync_keymap and keymap_file.exists():
            sync_keymap.import_keymap(keymap_file)
            applied.append("keymap")

        theme_file = mirror_dir / "theme.xml"
        if prefs.sync_theme and theme_file.exists():
            sync_theme.import_theme(theme_file)
            applied.append("theme")

        if prefs.sync_addons:
            remote_addons = sync_addons.read_addons_manifest(mirror_dir)
            if remote_addons:
                missing = sync_addons.diff_missing_addons(remote_addons)

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


class MYGITBLENDER_OT_checkout_snapshot(bpy.types.Operator):
    bl_idname = "mygitblender.checkout_snapshot"
    bl_label = "Restore This Snapshot"
    bl_description = "Apply the keymap/theme from this historical sync, without changing your git history"

    commit_sha: bpy.props.StringProperty()
    commit_label: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event,
            title="Restore snapshot",
            message=f"Apply keymap/theme from: {self.commit_label}?",
            confirm_text="Restore",
        )

    def execute(self, context):
        prefs = _get_prefs(context)
        mirror_dir = config_paths.get_mirror_dir()
        scratch_dir = mirror_dir.parent / "scratch_checkout"

        ok, msg = git_wrapper.checkout_worktree_at(mirror_dir, self.commit_sha, scratch_dir)
        if not ok:
            self.report({'ERROR'}, f"Could not check out snapshot: {msg}")
            return {'CANCELLED'}

        applied = []
        try:
            keymap_file = scratch_dir / "keymap.py"
            if prefs.sync_keymap and keymap_file.exists():
                sync_keymap.import_keymap(keymap_file)
                applied.append("keymap")

            theme_file = scratch_dir / "theme.xml"
            if prefs.sync_theme and theme_file.exists():
                sync_theme.import_theme(theme_file)
                applied.append("theme")
        finally:
            git_wrapper.remove_worktree(mirror_dir, scratch_dir)

        if applied:
            self.report({'INFO'}, f"Restored from snapshot: {', '.join(applied)}")
        else:
            self.report({'WARNING'}, "Nothing to restore from that snapshot")
        return {'FINISHED'}


class MYGITBLENDER_MT_history(bpy.types.Menu):
    bl_idname = "MYGITBLENDER_MT_history"
    bl_label = "Sync History"

    def draw(self, context):
        layout = self.layout
        mirror_dir = config_paths.get_mirror_dir()

        if not (mirror_dir / ".git").exists():
            layout.label(text="No history yet - push first")
            return

        ok, out = git_wrapper.log(mirror_dir, count=15)
        lines = [line for line in out.strip().splitlines() if line] if ok else []
        if not lines:
            layout.label(text="No history yet - push first")
            return

        for line in lines:
            parts = line.split("|", 2)
            if len(parts) != 3:
                continue
            sha, date, subject = parts
            label = f"{date[:16]}  {subject}"
            op = layout.operator("mygitblender.checkout_snapshot", text=label)
            op.commit_sha = sha
            op.commit_label = label


class MYGITBLENDER_OT_browse_history(bpy.types.Operator):
    bl_idname = "mygitblender.browse_history"
    bl_label = "History"
    bl_description = "Browse previous syncs and restore an older one"

    def execute(self, context):
        bpy.ops.wm.call_menu(name=MYGITBLENDER_MT_history.bl_idname)
        return {'FINISHED'}


classes = (
    MYGITBLENDER_OT_push,
    MYGITBLENDER_OT_pull,
    MYGITBLENDER_OT_checkout_snapshot,
    MYGITBLENDER_MT_history,
    MYGITBLENDER_OT_browse_history,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
