# MyGitBlender

I got tired of setting up Blender from scratch every time I switched computers. Re-downloading add-ons, re-binding hotkeys, rebuilding my theme, all of it, over and over. MyGitBlender fixes that by saving your Blender setup to a GitHub repo. When you're on a new machine, you just pull it back down instead of doing everything by hand again.

It syncs your hotkeys, your theme, your start-up file, your general preferences, and a list of the add-ons you have installed. Everything is stored as a normal git repo, so you also get a full history of your config and can roll back to an older version whenever you want.

Works with Blender 4.2 and up. Built and tested on 5.1.

## Features

**Push and Pull buttons** live right in `Edit > Preferences > Add-ons`. Push saves your current setup to GitHub, Pull brings it back down. Both run in the background so Blender doesn't freeze while git does its thing.

**Selective sync.** You choose what gets synced: hotkeys, theme, add-on list, start-up file, preferences, any combination.

**A status line** tells you when the last sync happened, which machine did it, and which Blender version it came from.

**Conflict protection.** If another machine already pushed changes you haven't pulled yet, Push will stop you before you overwrite them. Pull warns you the same way if you have local changes that haven't been saved.

**Version tagging.** If you pull a config that was pushed from a different Blender version, you'll get a heads up before it applies.

**Sync history.** Every push is logged with a timestamp, the machine it came from, and what changed. You can browse old syncs and restore any of them.

**An add-on manifest.** Every push writes out `addons.json` and a readable `addons.md` listing everything you have installed. If some of those add-ons are missing after a pull and they're available from an online repo (like extensions.blender.org), the add-on offers to reinstall them for you with one click.

**Automatic backups.** Before every Pull (or snapshot restore), your current config gets backed up locally first. If something looks wrong afterward, hit Undo Last Pull and you're back to where you were.

**A Setup Health Check.** One button checks that git is installed, your identity is set, and your repo is reachable. If anything's wrong, it tells you exactly what and how to fix it. If git itself is missing, there's an Install Git button right there too, it uses Windows's built in installer (winget) or macOS's developer tools installer, so you don't have to go find and run anything yourself.

**Plain language errors.** No raw git output dumped in your face. Common problems like being offline, a bad sign in, or a wrong URL get explained in normal English. Git also can't hang Blender waiting on a password prompt that will never come.

**A push reminder.** If it's been a while and your config has changed but you haven't pushed, you'll get a gentle nudge.

**First time setup wizard.** On a fresh machine, just paste in your repo URL and everything gets pulled and applied in one go.

## How to use it

**Setting it up for the first time.** Create a private GitHub repo (private is a good idea since your keymap and add-on list say a lot about your setup). Paste the repo URL into the MyGitBlender panel. Run Setup Health Check to make sure git is ready to go. Then hit Push.

**Day to day.** Change a hotkey, tweak your theme, install something new, whatever. When you want to save it, click Push. That's really the whole workflow.

**Moving to a new computer.** Install Blender and git (GitHub Desktop is an easy way to get both git and sign in working). Install the MyGitBlender add-on. Open the panel and click First Time Setup, then paste your repo URL. Your hotkeys and theme apply right away. Restart Blender once to pick up your start-up file and preferences. If any add-ons are missing, you'll get a prompt to reinstall the ones available online, and `addons.md` in your repo lists anything you'll need to grab manually.

**If something goes wrong.** Undo Last Pull puts your config back to how it was right before the last pull. The History browser lets you go back further, to any earlier sync. And the conflict and version warnings are there to stop you from overwriting something by accident in the first place.

## Install

1. Download or zip the `MyGitBlender` folder. It needs to have `blender_manifest.toml` at its root.
2. In Blender, go to `Edit > Preferences > Get Extensions`, open the dropdown in the top right, and choose **Install from Disk**. Pick the zip.
3. Enable it. You'll see a **MyGitBlender** section under `Edit > Preferences > Add-ons`.
4. You'll need git installed on your computer and signed in to GitHub already (GitHub Desktop or `gh auth login` both work fine for this).

## Project structure

| File | Role |
|------|------|
| `__init__.py` | Registration entry point |
| `preferences.py` | The add-on's preferences UI: repo URL, sync checkboxes, buttons, status line |
| `operators.py` | Push/Pull (runs in the background), history browser, snapshot restore, missing add-on installer, setup wizard |
| `git_wrapper.py` | Subprocess wrapper around git, has no dependency on `bpy` |
| `config_paths.py` | Works out where Blender's config lives and where the local mirror repo goes |
| `sync_keymap.py` / `sync_theme.py` | Export and import keymap/theme using Blender's own text formats |
| `sync_binary.py` | Copies `startup.blend` / `userpref.blend`, with hash based change detection |
| `sync_addons.py` | Builds the add-on manifest (`addons.json` / `addons.md`) and figures out what's missing |
| `conflict.py` | Detects a diverged remote or unsaved local changes |
| `version_tag.py` | Sync metadata (`sync_manifest.json`), commit messages, and the panel's status text |
| `reminder.py` | The periodic reminder popup for unsynced changes |
| `health.py` | Setup Health Check, Set Git Identity, and Install Git |
| `backup.py` | Pre-Pull safety backups and the Undo Last Pull restore |
| `blender_manifest.toml` | Extension metadata |

## License

GPL-2.0-or-later, same as Blender itself. See the LICENSE file.
