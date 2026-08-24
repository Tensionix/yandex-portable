#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


PRESERVE_ROOT_FILES = {
    'RELEASE_CHECKLIST.md',
    'RELEASE_POLICY.md',
    'THIRD_PARTY_NOTICES.md',
    '_records.json',
}


def info(message: str) -> None:
    print(f"[INFO] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Remove stale collected license package folders not present in current records.')
    parser.add_argument('--project-root')
    parser.add_argument('--output-root')
    return parser.parse_args()


def keep_license_dirs(records_path: Path) -> set[str]:
    if not records_path.exists():
        return set()
    records = json.loads(records_path.read_text(encoding='utf-8'))
    keep: set[str] = set()
    for record in records:
        for item in record.get('license_files', []) or []:
            parts = Path(item).parts
            if len(parts) >= 2 and parts[0] == 'licenses':
                keep.add(parts[1])
    return keep


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[2]
    output_root = Path(args.output_root).resolve() if args.output_root else project_root
    licenses_root = output_root / 'licenses'
    records_path = licenses_root / '_records.json'

    if not licenses_root.exists():
        warn(f'licenses folder not found: {licenses_root}')
        return 1

    keep_dirs = keep_license_dirs(records_path)
    removed = 0
    for child in sorted(licenses_root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_file():
            if child.name not in PRESERVE_ROOT_FILES:
                warn(f'Unexpected root file kept as-is: {child}')
            continue
        if not child.is_dir():
            continue
        if child.name in keep_dirs:
            continue
        try:
            shutil.rmtree(child)
            removed += 1
        except PermissionError:
            warn(f'Could not remove stale license folder: {child}')

    info(f'Removed stale license folders: {removed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
