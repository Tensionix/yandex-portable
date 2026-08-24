# Audion GUI Portable Porting Checklist

Use this checklist when moving another Audion Python project onto the GUI-capable portable template.

## Runtime

1. Build or install the portable Python runtime.
2. Install GUI dependencies from `install\requirements_full.in`.
3. Verify `nicegui`, `pywebview`, and the GUI smoke path with:

```bat
install\verify_portable_env.cmd
```

The verify script runs `system_core\doctor.py` and, when present, `system_core\ui_nicegui\app.py --smoke`.

## PowerShell For Native Pickers

The project core should not need PowerShell for business logic.

PowerShell is used for native Windows file/folder picker dialogs and some build helper scripts. The preferred lookup order for GUI dialogs is:

1. `system_core\powershell\pwsh.exe`
2. `pwsh.exe` from `PATH`
3. built-in `powershell.exe`

Install portable PowerShell from the builder menu:

```bat
builder_main.cmd
```

Choose:

```text
[04] POWERSHELL
```

or run directly:

```bat
install\Install-Portable-PowerShell.cmd
```

## GUI Shell

Keep the GUI as a shell over the CLI, not as a second business-logic implementation.

- CLI commands remain the source of truth.
- GUI operations should call service wrappers that invoke existing CLI code.
- Keep logs visible in the GUI.
- Keep reports in `output\` and machine-readable GUI artifacts in `report\`.
- Add `--smoke` to GUI entry points so portable verification can run without opening a browser.
- Long-running operations must not depend on the child screen or button slot that launched them. Store completion in shared state/logs and deliver notifications through the template `safe_notify`/live NiceGUI clients.
- Do not show notifications for simple folder-open buttons (`INPUT`, `OUTPUT`, `LOGS`, `CONFIG`, `REPORT`, `TOOLS`); the file manager opening is enough feedback. Folder picking, staging, custom path selection, and import actions may still use notifications because they change project state.

## Recommended GUI Controls

- Use folder/file pickers for source and target paths.
- Store path history in `config\path_history.json` when workflows use repeated paths.
- Support pinned paths for frequent network/NAS/external-drive locations.
- Add import/export for path history and profile bundles when users move between machines.
- Put destructive operations behind clear labels and dry-run previews.
- Prefer grouped extension checkboxes over long flat checkbox lists.
- Group related single-choice controls together, such as provider key and model.
- Use radio buttons for small fixed choices and searchable dropdowns for long/dynamic lists.
- Keep rare numeric/manual parameters in a lower compact block.
- Avoid duplicate actions for the same outcome, including duplicate favorites controls.

## Builder Integration

Recommended builder menu entries for GUI-capable projects:

- build portable env
- install portable PowerShell
- install portable offline
- verify portable env
- check/fix CMD encoding
- update fzf
- collect/deduplicate/prune licenses
- make release archive
- open runtime/wheelhouse/licenses/release folders
- project launcher

## Release Notes

For source-only repositories, portable Python, portable PowerShell, wheelhouse contents, logs, reports, and release archives may be omitted.

For fully portable binary releases, include:

- `runtime\`
- `system_core\powershell\` if portable picker/build independence is required
- `wheelhouse\` if offline reinstall is required
- third-party notices for Python, PowerShell, NiceGUI, pywebview, fzf, and installed Python packages
