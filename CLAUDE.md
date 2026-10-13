# Deskfinity — notes for Claude

Desktop icon organizer for Windows: one file, `deskfinity.py` (Python 3.9+, PyQt6).
Boxes on the wallpaper hold shortcuts; desktop items dropped in are moved into
the box's storage folder.

## Owner's setup
- Working copy of the app: `E:\ClaudeFiles\Deskfinity` — the built
  `Deskfinity.exe` runs from there.
- Portable data: `E:\ClaudeFiles\Deskfinity\DeskfinityData` (boxes.json,
  storage\, deskfinity.log). Never delete or overwrite it; it holds the user's
  real shortcuts.
- The owner writes in Russian; answer in Russian.

## Workflow after every change
1. `python -m pyflakes deskfinity.py tests` and
   `python -m unittest discover -s tests` (all must pass; WinAPI tests in
   `tests/test_windows.py` run only on Windows).
2. Build: `pyinstaller --noconfirm --onefile --windowed --name Deskfinity deskfinity.py`.
3. Restart the owner's copy: stop only the `Deskfinity.exe` processes whose
   path is `E:\ClaudeFiles\Deskfinity\Deskfinity.exe`, **by PID** (a one-file
   exe runs as two processes). Never kill by process name — pythonw/python
   also run other tools. Copy `dist\Deskfinity.exe` over it (keep the previous
   one as `Deskfinity.exe.old`), start it, check the log for "Starting Deskfinity".
4. Tell the owner what to check; commit and push only after they confirm.

## Conventions
- Every UI string goes through `tr("русский", "English")`; a test fails otherwise.
- Never name anything `tr` (shadows the function).
- One feature or fix per commit, with tests in `tests/` (headless, Qt offscreen).
- Branches: work lands in PR #1 (`fix/safety-and-stability`) after the owner
  confirms on the PC; `feature/polish` is the current branch on top of it.
- CI (`.github/workflows/windows-build.yml`) tests on Linux + Windows, builds the
  exe, publishes it to the `dev` pre-release on every push and to a release on
  `v*` tags.
