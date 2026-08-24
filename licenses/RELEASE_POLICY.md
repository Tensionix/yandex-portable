# Release Policy

This project publishes user-ready packages through GitHub Releases.

Repository source archives are not the intended delivery format for end users.

## Core rule

Licensing is generated or updated from the finalized staged release contents.

If a third-party component is present in the final release package, it must be covered in release licensing.

Existing license files may be retained when harmless, but the generated notices should reflect the detected staged release contents.

## Always cover when present

The following baseline components must always be covered when present in the final package:

- PowerShell
- Python Embedded
- fzf
- NiceGUI

## Also cover when present

All third-party components actually present in the final release package must be covered, including:

- Python wheels in wheelhouse or bundled cache
- installed Python packages shipped inside runtime
- bundled runtimes
- bundled tools
- helper binaries and other external components

## Required release licensing outputs

The final staged release package must contain:

- `THIRD_PARTY_NOTICES.md`
- `licenses/`
- the project `LICENSE`

## Tooling location

Release licensing tools are stored in:

- `system_core\license\collect_third_party_licenses.py`
- `system_core\license\Run-Collect-ThirdPartyLicenses.cmd`
- `system_core\license\Run-Deduplicate-ThirdPartyLicenses.cmd`
- `system_core\license\manifest.json`

## Safety-first rule

This project includes third-party licensing based on actual presence in the release package, even if attribution is not believed to be strictly required.

The policy is presence-based, not minimum-legal-theory based.


## License Collector

This template now uses a Python-only license collector:

- Python engine: `system_core/license/collect_third_party_licenses.py`

The wrapper now dispatches to the Python collector only. PowerShell engine mode was removed from the standard release flow.
