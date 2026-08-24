#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def info(message: str) -> None:
    print(f"[INFO] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def normalize_text_hash(path: Path) -> str:
    data = path.read_bytes()
    try:
        text = data.decode('utf-8-sig')
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = '\n'.join(line.rstrip() for line in text.split('\n')).strip() + '\n'
        payload = text.encode('utf-8')
    except UnicodeDecodeError:
        payload = data
    return hashlib.sha256(payload).hexdigest()


def markdown_table_cell(value: object) -> str:
    text = str(value if value is not None else '')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = ' '.join(line.strip() for line in text.split('\n') if line.strip())
    return text.replace('|', '\\|')


def file_priority(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    if 'license' in name:
        p = 0
    elif 'copying' in name:
        p = 1
    elif 'notice' in name:
        p = 2
    elif 'authors' in name:
        p = 3
    else:
        p = 9
    return (p, len(path.as_posix()), path.as_posix().lower())


def keep_winner(paths: list[Path]) -> Path:
    return sorted(paths, key=file_priority)[0]


def deduplicate_bucketed_files(files: list[Path]) -> tuple[dict[str, str], int]:
    remap: dict[str, str] = {}
    removed_count = 0
    name_size_buckets: dict[str, list[Path]] = {}
    for file in files:
        name_size_buckets.setdefault(normalize_text_hash(file), []).append(file)

    for same_name_size in name_size_buckets.values():
        if len(same_name_size) < 2:
            continue
        keeper = keep_winner(same_name_size)
        keeper_rel = keeper
        for duplicate in same_name_size:
            if duplicate == keeper:
                continue
            try:
                duplicate.unlink(missing_ok=True)
            except PermissionError:
                warn(f"Could not remove duplicate license file: {duplicate}")
                continue
            remap[duplicate.as_posix()] = keeper_rel.as_posix()
            removed_count += 1
    return remap, removed_count


def write_notices(records: list[dict], notice_path: Path) -> None:
    lines = [
        '# THIRD_PARTY_NOTICES',
        '',
        'This file lists third-party components redistributed with this package.',
        '',
        '| Component | Version | License | Source | License files |',
        '|---|---:|---|---|---|',
    ]
    for record in records:
        files = record.get('license_files', []) or []
        files_cell = '<br>'.join(f'`{item}`' for item in files) if files else 'None found automatically'
        lines.append(
            f"| {markdown_table_cell(record.get('name', ''))} | {markdown_table_cell(record.get('version', ''))} | "
            f"{markdown_table_cell(record.get('license', 'UNKNOWN'))} | {markdown_table_cell(record.get('source', ''))} | {files_cell} |"
        )
    lines.extend([
        '',
        '## Policy',
        '',
        '- Add missing baseline notices for PowerShell, Python Embedded, fzf, and NiceGUI when they are present in the final release package.',
        '- Include every third-party component actually present in the final release package, even when attribution may not be strictly required.',
        '- Update this file after the final release contents are staged.',
        '- Deduplicate only exact content matches for the same package and version.',
        '',
    ])
    notice_path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Deduplicate collected third-party licenses by normalized content hash.')
    parser.add_argument('--project-root')
    parser.add_argument('--output-root')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[2]
    output_root = Path(args.output_root).resolve() if args.output_root else project_root
    licenses_root = output_root / 'licenses'
    records_path = licenses_root / '_records.json'
    notices_path = licenses_root / 'THIRD_PARTY_NOTICES.md'

    if not licenses_root.exists():
        warn(f'licenses folder not found: {licenses_root}')
        return 1

    remap: dict[str, str] = {}
    removed_count = 0
    package_dirs = sorted([p for p in licenses_root.iterdir() if p.is_dir()])
    for package_dir in package_dirs:
        files = [p for p in package_dir.rglob('*') if p.is_file()]
        local_remap, local_removed = deduplicate_bucketed_files(files)
        removed_count += local_removed
        for duplicate, keeper in local_remap.items():
            remap[(output_root / duplicate).relative_to(output_root).as_posix()] = (output_root / keeper).relative_to(output_root).as_posix()

    if records_path.exists():
        records = json.loads(records_path.read_text(encoding='utf-8'))
        for record in records:
            updated: list[str] = []
            seen: set[str] = set()
            for item in record.get('license_files', []) or []:
                candidate = remap.get(item, item)
                abs_path = output_root / candidate
                if not abs_path.exists():
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                updated.append(candidate)
            record['license_files'] = updated
        records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
        write_notices(records, notices_path)
        info(f'Updated: {records_path}')
        info(f'Updated: {notices_path}')

    info(f'Removed duplicate files: {removed_count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
