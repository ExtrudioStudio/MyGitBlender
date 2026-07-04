import bpy

from . import config_paths
from . import git_wrapper


def _get_prefs(context):
    return context.preferences.addons[__package__].preferences


def run_checks(context):
    """Returns (results, identity_missing, git_missing) where results is a
    list of (ok, label, hint) tuples."""
    prefs = _get_prefs(context)
    results = []
    identity_missing = False

    if not git_wrapper.git_available():
        results.append((False, "Git is not installed",
                        "Use the Install Git button below"))
        # Every other check needs the git executable - stop here.
        return results, identity_missing, True
    results.append((True, "Git is installed", ""))

    name, email = git_wrapper.get_identity(config_paths.get_mirror_dir())
    if name and email:
        results.append((True, f"Git identity: {name} <{email}>", ""))
    else:
        identity_missing = True
        results.append((False, "Git identity (name/email) not set",
                        "Use the Set Git Identity button below"))

    repo_url = prefs.repo_url.strip()
    if not repo_url:
        results.append((False, "No repo URL set",
                        "Paste your GitHub repo URL in the field above"))
        return results, identity_missing, False
    results.append((True, "Repo URL is set", ""))

    ok, err = git_wrapper.check_remote(repo_url, timeout=10.0)
    if ok:
        results.append((True, "Repo is reachable and you have access", ""))
    else:
        results.append((False, "Can't reach the repo", err))

    return results, identity_missing, False


class MYGITBLENDER_OT_health_check(bpy.types.Operator):
    bl_idname = "mygitblender.health_check"
    bl_label = "Setup Health Check"
    bl_description = (
        "Check that git is installed, your identity is set, and the repo is "
        "reachable - with instructions for anything that isn't"
    )

    def execute(self, context):
        results, identity_missing, git_missing = run_checks(context)
        problems = sum(1 for ok, _, _ in results if not ok)

        def draw(menu, _context):
            col = menu.layout.column()
            for ok, label, hint in results:
                col.label(text=label, icon='CHECKMARK' if ok else 'CANCEL')
                if hint:
                    col.label(text=f"      {hint}")
            if git_missing:
                col.separator()
                col.operator_context = 'INVOKE_DEFAULT'
                col.operator("mygitblender.install_git", icon='IMPORT')
            if identity_missing:
                col.separator()
                col.operator_context = 'INVOKE_DEFAULT'
                col.operator("mygitblender.set_git_identity", icon='USER')

        context.window_manager.popup_menu(
            draw,
            title="All good - ready to sync" if problems == 0 else f"{problems} issue(s) found",
            icon='CHECKMARK' if problems == 0 else 'ERROR',
        )

        if problems == 0:
            self.report({'INFO'}, "Health check: everything looks good")
        else:
            self.report({'WARNING'}, f"Health check: {problems} issue(s) found - see popup")
        return {'FINISHED'}


class MYGITBLENDER_OT_install_git(bpy.types.Operator):
    bl_idname = "mygitblender.install_git"
    bl_label = "Install Git"
    bl_description = (
        "Install git for you (via Windows winget or macOS's developer tools "
        "installer). You may see a system prompt to approve it"
    )

    def execute(self, context):
        launched, mode = git_wrapper.launch_git_installer()

        if launched:
            self.report(
                {'INFO'},
                "Installing git - approve any system prompt that appears, "
                "then run Setup Health Check again when it's done",
            )
            return {'FINISHED'}

        import webbrowser
        webbrowser.open("https://git-scm.com/downloads")
        self.report(
            {'INFO'},
            "Opened the git download page - run the installer, then Setup Health Check again",
        )
        return {'FINISHED'}


class MYGITBLENDER_OT_set_git_identity(bpy.types.Operator):
    bl_idname = "mygitblender.set_git_identity"
    bl_label = "Set Git Identity"
    bl_description = (
        "Set the name/email git records on your syncs. Applied only to "
        "MyGitBlender's own repo - your global git setup is not touched"
    )

    git_name: bpy.props.StringProperty(name="Name")
    git_email: bpy.props.StringProperty(name="Email")

    def invoke(self, context, event):
        prefs = _get_prefs(context)
        name, email = git_wrapper.get_identity(config_paths.get_mirror_dir())
        self.git_name = prefs.git_user_name or name
        self.git_email = prefs.git_user_email or email
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.git_name.strip()
        email = self.git_email.strip()
        if not name or not email:
            self.report({'ERROR'}, "Both name and email are needed")
            return {'CANCELLED'}

        prefs = _get_prefs(context)
        prefs.git_user_name = name
        prefs.git_user_email = email

        mirror_dir = config_paths.get_mirror_dir()
        if (mirror_dir / ".git").exists():
            git_wrapper.set_local_identity(mirror_dir, name, email)
            self.report({'INFO'}, f"Git identity set: {name} <{email}>")
        else:
            self.report({'INFO'}, f"Saved - will be applied when the sync repo is created")
        return {'FINISHED'}


classes = (
    MYGITBLENDER_OT_health_check,
    MYGITBLENDER_OT_install_git,
    MYGITBLENDER_OT_set_git_identity,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
