import threading

import bpy

from . import backup
from . import config_paths
from . import conflict
from . import git_wrapper
from . import sync_addons
from . import sync_binary
from . import sync_keymap
from . import sync_theme
from . import version_tag

# Only one git job at a time; the reminder timer also checks this.
_busy = False

# Missing add-ons found by the last Pull. The "installable" subset is what
# the panel's Install Missing Add-ons button offers to reinstall.
_last_missing = []
_last_missing_installable = []


def is_busy() -> bool:
    return _busy


def get_cached_installable_missing() -> list:
    return _last_missing_installable


def _get_prefs(context):
    return context.preferences.addons[__package__].preferences


def _installable_subset(context, missing):
    """Missing add-ons that came from an enabled remote extensions repo,
    so Blender can reinstall them for us."""
    remote_repos = {
        repo.module
        for repo in context.preferences.extensions.repos
        if repo.enabled and repo.use_remote_url
    }
    return [e for e in missing if e.get("is_extension") and e.get("repo") in remote_repos]


def _set_missing_cache(context, missing):
    global _last_missing, _last_missing_installable
    _last_missing = missing
    _last_missing_installable = _installable_subset(context, missing)


def _ensure_repo_with_identity(prefs, mirror_dir):
    """ensure_repo + re-apply the stored mirror-local git identity (a fresh
    clone starts without one, and we never touch the global git config)."""
    ok, msg = git_wrapper.ensure_repo(mirror_dir, prefs.repo_url.strip())
    if ok and prefs.git_user_name.strip() and prefs.git_user_email.strip():
        git_wrapper.set_local_identity(
            mirror_dir, prefs.git_user_name.strip(), prefs.git_user_email.strip())
    return ok, msg


class _Worker(threading.Thread):
    def __init__(self, fn):
        super().__init__(daemon=True)
        self._fn = fn
        self.result = None
        self.error = None
        self.done = False

    def run(self):
        try:
            self.result = self._fn()
        except Exception as ex:
            self.error = str(ex)
        self.done = True


def _start_job(op, context, worker):
    global _busy
    _busy = True
    op._worker = worker
    op._timer = context.window_manager.event_timer_add(0.25, window=context.window)
    context.window_manager.modal_handler_add(op)
    worker.start()
    return {'RUNNING_MODAL'}


def _end_job(op, context):
    global _busy
    _busy = False
    if op._timer is not None:
        context.window_manager.event_timer_remove(op._timer)
        op._timer = None


class MYGITBLENDER_OT_push(bpy.types.Operator):
    bl_idname = "mygitblender.push"
    bl_label = "Push"
    bl_description = "Save current Blender config to the GitHub repo (runs in the background)"

    _worker = None
    _timer = None
    _changed = None

    def _prepare(self, context):
        """Validate, export the selected categories into the mirror, and build
        the commit message. Returns (mirror_dir, changed, commit_msg); on
        failure mirror_dir is None and changed is (report_level, message)."""
        prefs = _get_prefs(context)
        repo_url = prefs.repo_url.strip()
        if not repo_url:
            return None, ('ERROR', "Set a GitHub Repo URL in the add-on preferences first"), None

        mirror_dir = config_paths.get_mirror_dir()
        ok, msg = _ensure_repo_with_identity(prefs, mirror_dir)
        if not ok:
            return None, ('ERROR', git_wrapper.humanize_git_error(msg)), None

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
        if prefs.sync_startup and sync_binary.export_startup(mirror_dir):
            changed.append("startup file")
        if prefs.sync_preferences and sync_binary.export_preferences(mirror_dir):
            changed.append("preferences")

        if not changed:
            return None, ('WARNING', "Nothing selected to sync - check a category first"), None

        version_tag.write_version_tag(mirror_dir)
        return mirror_dir, changed, version_tag.build_commit_message(changed)

    @staticmethod
    def _work(mirror_dir, commit_msg):
        """Network + commit phase. No bpy access - safe to run off-thread."""
        git_wrapper.fetch(mirror_dir)
        if git_wrapper.remote_ahead_count(mirror_dir) > 0:
            return 'error', "Remote has changes you haven't pulled yet - Pull first, then Push"

        committed, res = git_wrapper.commit_all(mirror_dir, commit_msg)
        if not committed and res != "nothing to commit":
            return 'error', git_wrapper.humanize_git_error(res)

        ok, out = git_wrapper.push(mirror_dir)
        if not ok:
            return 'error', git_wrapper.humanize_git_error(out)
        return 'ok', committed

    def _report_result(self, status, payload):
        if status == 'error':
            self.report({'ERROR'}, payload)
            return {'CANCELLED'}
        if payload:
            self.report({'INFO'}, f"Pushed {', '.join(self._changed)} to GitHub")
        else:
            self.report({'INFO'}, "Already up to date with GitHub")
        return {'FINISHED'}

    def invoke(self, context, event):
        if _busy:
            self.report({'ERROR'}, "A sync is already running - wait for it to finish")
            return {'CANCELLED'}

        mirror_dir, changed, commit_msg = self._prepare(context)
        if mirror_dir is None:
            level, msg = changed
            self.report({level}, msg)
            return {'CANCELLED'}

        self._changed = changed
        self.report({'INFO'}, "Pushing to GitHub in the background...")
        return _start_job(self, context, _Worker(lambda: self._work(mirror_dir, commit_msg)))

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        if not self._worker.done:
            return {'RUNNING_MODAL'}

        _end_job(self, context)
        if self._worker.error:
            self.report({'ERROR'}, f"Push failed: {self._worker.error}")
            return {'CANCELLED'}
        status, payload = self._worker.result
        return self._report_result(status, payload)

    def execute(self, context):
        """Synchronous path for scripts (blocks on network)."""
        if _busy:
            self.report({'ERROR'}, "A sync is already running - wait for it to finish")
            return {'CANCELLED'}

        mirror_dir, changed, commit_msg = self._prepare(context)
        if mirror_dir is None:
            level, msg = changed
            self.report({level}, msg)
            return {'CANCELLED'}

        self._changed = changed
        status, payload = self._work(mirror_dir, commit_msg)
        return self._report_result(status, payload)


class MYGITBLENDER_OT_pull(bpy.types.Operator):
    bl_idname = "mygitblender.pull"
    bl_label = "Pull"
    bl_description = "Restore Blender config from the GitHub repo (checks run in the background)"

    skip_checks: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    _worker = None
    _timer = None

    def invoke(self, context, event):
        if _busy:
            self.report({'ERROR'}, "A sync is already running - wait for it to finish")
            return {'CANCELLED'}

        prefs = _get_prefs(context)
        repo_url = prefs.repo_url.strip()
        if not repo_url:
            self.report({'ERROR'}, "Set a GitHub Repo URL in the add-on preferences first")
            return {'CANCELLED'}

        mirror_dir = config_paths.get_mirror_dir()
        first_time = not (mirror_dir / ".git").exists()
        ok, msg = _ensure_repo_with_identity(prefs, mirror_dir)
        if not ok:
            self.report({'ERROR'}, git_wrapper.humanize_git_error(msg))
            return {'CANCELLED'}

        # A fresh clone is already up to date and has no local state worth
        # protecting; "Pull anyway" already ran the checks and was confirmed.
        if first_time or self.skip_checks:
            return self.execute(context)

        self.report({'INFO'}, "Checking GitHub in the background...")
        return _start_job(self, context, _Worker(lambda: git_wrapper.fetch(mirror_dir)))

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        if not self._worker.done:
            return {'RUNNING_MODAL'}

        _end_job(self, context)
        if self._worker.error:
            self.report({'ERROR'}, f"Fetch failed: {self._worker.error}")
            return {'CANCELLED'}
        ok, out = self._worker.result
        if not ok:
            self.report({'ERROR'}, git_wrapper.humanize_git_error(out))
            return {'CANCELLED'}

        prefs = _get_prefs(context)
        mirror_dir = config_paths.get_mirror_dir()

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
            _show_pull_warning_popup(context, warnings)
            return {'CANCELLED'}

        return self.execute(context)

    def execute(self, context):
        prefs = _get_prefs(context)
        repo_url = prefs.repo_url.strip()
        if not repo_url:
            self.report({'ERROR'}, "Set a GitHub Repo URL in the add-on preferences first")
            return {'CANCELLED'}

        mirror_dir = config_paths.get_mirror_dir()
        ok, msg = _ensure_repo_with_identity(prefs, mirror_dir)
        if not ok:
            self.report({'ERROR'}, git_wrapper.humanize_git_error(msg))
            return {'CANCELLED'}

        ok, out = git_wrapper.merge_ff(mirror_dir)
        if not ok:
            self.report({'ERROR'}, git_wrapper.humanize_git_error(out))
            return {'CANCELLED'}

        # Safety net: snapshot the current live config so this Pull can be
        # undone. If the backup can't be taken, don't touch anything.
        try:
            backup.make_backup(prefs)
        except Exception as ex:
            self.report({'ERROR'}, f"Pull aborted - couldn't back up current config: {ex}")
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
        _set_missing_cache(context, missing)

        restart_needed = []
        if prefs.sync_startup and sync_binary.import_startup(mirror_dir):
            restart_needed.append("startup file")
        if prefs.sync_preferences and sync_binary.import_preferences(mirror_dir):
            restart_needed.append("preferences")
        applied.extend(restart_needed)

        if applied:
            msg = f"Applied: {', '.join(applied)}"
        else:
            msg = "Nothing to apply yet - push from another machine first"

        if missing:
            names = ", ".join(e["name"] for e in missing[:5])
            more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            msg += f". Missing add-ons: {names}{more}"
            if _last_missing_installable:
                msg += " - see popup"
                manual_only = [e for e in missing if e not in _last_missing_installable]
                _show_install_confirm_popup(context, _last_missing_installable, manual_only)

        if restart_needed:
            msg += f". Restart Blender NOW to apply {', '.join(restart_needed)} - don't save preferences before restarting"

        self.report({'WARNING'} if (missing or restart_needed) else {'INFO'}, msg)
        return {'FINISHED'}


def _show_install_confirm_popup(context, installable, manual_only):
    wm = context.window_manager
    if not wm or not wm.windows:
        return

    def draw(menu, _context):
        col = menu.layout.column()
        col.label(text=f"{len(installable)} missing add-on(s) can be reinstalled:")
        for entry in installable[:10]:
            col.label(text=entry["name"], icon='PLUGIN')
        if len(installable) > 10:
            col.label(text=f"...and {len(installable) - 10} more")
        if manual_only:
            col.separator()
            col.label(text=f"{len(manual_only)} other(s) need manual install - see addons.md")
        col.separator()
        col.operator_context = 'INVOKE_DEFAULT'
        col.operator(
            "mygitblender.install_missing",
            text=f"Install All ({len(installable)})",
            icon='IMPORT',
        )

    wm.popup_menu(draw, title="Missing add-ons found", icon='QUESTION')


def _show_pull_warning_popup(context, warnings):
    def draw(menu, _context):
        col = menu.layout.column()
        for line in warnings:
            col.label(text=line)
        col.label(text="Pulling now may overwrite or not apply cleanly.")
        col.separator()
        col.operator_context = 'INVOKE_DEFAULT'
        op = col.operator("mygitblender.pull", text="Pull Anyway", icon='IMPORT')
        op.skip_checks = True

    context.window_manager.popup_menu(draw, title="Heads up before pulling", icon='ERROR')


class MYGITBLENDER_OT_install_missing(bpy.types.Operator):
    bl_idname = "mygitblender.install_missing"
    bl_label = "Install Missing Add-ons"
    bl_description = (
        "Reinstall missing add-ons that came from an online extensions repository "
        "(e.g. extensions.blender.org). Others must be reinstalled manually - see addons.md"
    )

    @staticmethod
    def _try_install(repo, entry):
        """Install one package and verify it actually landed on disk.
        extensions.package_install returns FINISHED even when the package id
        is unknown (it only prints to the console), so the return value can't
        be trusted - check the package directory instead."""
        from pathlib import Path

        pkg_id = entry["module"].split(".")[-1]
        try:
            bpy.ops.extensions.package_install(
                repo_directory=repo.directory,
                pkg_id=pkg_id,
                enable_on_install=entry.get("enabled", True),
            )
        except Exception:
            return False
        return (Path(repo.directory) / pkg_id).is_dir()

    def execute(self, context):
        global _last_missing_installable
        targets = list(_last_missing_installable)
        if not targets:
            self.report({'INFO'}, "No reinstallable add-ons - Pull first to refresh the list")
            return {'CANCELLED'}

        repos = {
            repo.module: repo
            for repo in context.preferences.extensions.repos
            if repo.enabled and repo.use_remote_url
        }

        # Already installed but disabled: enabling is all that's needed.
        import addon_utils
        installed_modules = {m.__name__ for m in addon_utils.modules(refresh=True)}

        installed = []
        failed = []
        to_download = []
        for entry in targets:
            if entry["module"] in installed_modules:
                try:
                    addon_utils.enable(entry["module"], default_set=True, persistent=True)
                    installed.append(entry["name"])
                except Exception:
                    failed.append(entry)
            else:
                to_download.append(entry)

        if to_download and not bpy.app.online_access:
            self.report({'ERROR'}, "Online access is disabled in Blender's System preferences")
            return {'CANCELLED'}

        download_failed = []
        for entry in to_download:
            if self._try_install(repos[entry["repo"]], entry):
                installed.append(entry["name"])
            else:
                download_failed.append(entry)

        if download_failed:
            # A stale or never-synced repo index makes installs fail silently
            # (typical on a brand-new machine). Refresh remotes and retry once.
            try:
                bpy.ops.extensions.repo_sync_all()
            except Exception:
                pass
            for entry in download_failed:
                if self._try_install(repos[entry["repo"]], entry):
                    installed.append(entry["name"])
                else:
                    failed.append(entry)

        _last_missing_installable = failed

        msg = f"Installed {len(installed)} add-on(s)"
        if failed:
            names = ", ".join(e["name"] for e in failed[:4])
            msg += f"; not available online: {names} - install these manually (see addons.md)"
        self.report({'WARNING'} if failed else {'INFO'}, msg)
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

        try:
            backup.make_backup(prefs)
        except Exception as ex:
            self.report({'ERROR'}, f"Restore aborted - couldn't back up current config: {ex}")
            return {'CANCELLED'}

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

            if prefs.sync_startup and sync_binary.import_startup(scratch_dir):
                applied.append("startup file (restart to apply)")
            if prefs.sync_preferences and sync_binary.import_preferences(scratch_dir):
                applied.append("preferences (restart to apply)")
        finally:
            git_wrapper.remove_worktree(mirror_dir, scratch_dir)

        if applied:
            self.report({'INFO'}, f"Restored from snapshot: {', '.join(applied)}")
        else:
            self.report({'WARNING'}, "Nothing to restore from that snapshot")
        return {'FINISHED'}


class MYGITBLENDER_OT_undo_pull(bpy.types.Operator):
    bl_idname = "mygitblender.undo_pull"
    bl_label = "Undo Last Pull"
    bl_description = "Restore your config exactly as it was right before the last Pull or snapshot restore"

    def invoke(self, context, event):
        latest = backup.latest_backup()
        if latest is None:
            self.report({'INFO'}, "No backup to restore yet")
            return {'CANCELLED'}
        _, info = latest
        taken = info.get("taken_at", "")[:16].replace("T", " ")
        return context.window_manager.invoke_confirm(
            self, event,
            title="Undo Last Pull",
            message=f"Restore your config from the backup taken {taken} (UTC)?",
            confirm_text="Restore",
        )

    def execute(self, context):
        latest = backup.latest_backup()
        if latest is None:
            self.report({'INFO'}, "No backup to restore yet")
            return {'CANCELLED'}

        backup_dir, _info = latest
        applied, restart_needed = backup.restore(backup_dir)
        if not applied:
            self.report({'WARNING'}, "Backup was empty - nothing restored")
            return {'CANCELLED'}

        msg = f"Restored: {', '.join(applied)}"
        if restart_needed:
            msg += (
                f". Restart Blender NOW to apply {', '.join(restart_needed)}"
                f" - don't save preferences before restarting"
            )
        self.report({'WARNING'} if restart_needed else {'INFO'}, msg)
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


class MYGITBLENDER_OT_first_time_setup(bpy.types.Operator):
    bl_idname = "mygitblender.first_time_setup"
    bl_label = "First-Time Setup (New Machine)"
    bl_description = "New machine? Enter your repo URL and pull every checked category in one go"

    repo_url: bpy.props.StringProperty(
        name="GitHub Repo URL",
        description="HTTPS URL of your MyGitBlender sync repo",
    )

    def invoke(self, context, event):
        self.repo_url = _get_prefs(context).repo_url
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "repo_url")

    def execute(self, context):
        if not self.repo_url.strip():
            self.report({'ERROR'}, "Enter a GitHub Repo URL")
            return {'CANCELLED'}

        _get_prefs(context).repo_url = self.repo_url.strip()

        # A fresh machine has no local config worth protecting, so skip
        # straight to Pull's execute() - no need for the conflict pre-checks.
        return bpy.ops.mygitblender.pull('EXEC_DEFAULT')


classes = (
    MYGITBLENDER_OT_push,
    MYGITBLENDER_OT_pull,
    MYGITBLENDER_OT_install_missing,
    MYGITBLENDER_OT_undo_pull,
    MYGITBLENDER_OT_checkout_snapshot,
    MYGITBLENDER_MT_history,
    MYGITBLENDER_OT_browse_history,
    MYGITBLENDER_OT_first_time_setup,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
