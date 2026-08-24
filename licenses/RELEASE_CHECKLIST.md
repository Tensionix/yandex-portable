# Release Checklist

Use this checklist before publishing a GitHub Release.

## Project readiness

- The project is finalized for the intended release.
- Final package contents are defined.
- Build-only and development-only files are excluded where possible.
- No secrets, private configs, temporary artifacts, or internal-only files remain.

## Licensing

- Release licensing is generated or updated only after release staging.
- `THIRD_PARTY_NOTICES.md` is present.
- `licenses/` is present.
- PowerShell licensing is covered when PowerShell is present.
- Python Embedded licensing is covered when Python Embedded is present.
- fzf licensing is covered when fzf is present.
- NiceGUI licensing is covered when NiceGUI is present.
- All other third-party components actually present in the final release package are covered.
- Existing harmless baseline license files are acceptable, but notices must match detected staged contents.

## Archive quality

- The final ZIP opens correctly.
- The package structure is clean and portable.
- The launcher starts.
- The main workflow passes a smoke test.
- No broken shortcuts, missing binaries, or empty placeholders remain.

## GitHub publishing

- The final ZIP is uploaded as a Release asset.
- Users are not expected to download the source archive.
- Release notes describe what the tool does and what is bundled.
- Checksums are attached when the project uses them.


## License Collector Engine Check

- Verify that the Python license collector works in the target environment.
- For cross-platform projects, validate the Python engine first.
- PowerShell engine validation is no longer part of the standard release flow.
