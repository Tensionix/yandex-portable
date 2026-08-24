#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

LICENSE_LIKE_RE = re.compile(r'(?i)(^|/)(license|copying|notice|authors)(\.[^/]+)?$')
DIST_INFO_FILE_RE = re.compile(r'(?i)\.dist-info/(LICENSE|COPYING|NOTICE|AUTHORS)(\.[^/]+)?$')
PRESERVE_ROOT_FILES = {'RELEASE_CHECKLIST.md', 'RELEASE_POLICY.md'}
GENERATED_ROOT_FILES = {'THIRD_PARTY_NOTICES.md', '_records.json'}


def info(message: str) -> None:
    print(f"[INFO] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip().lower())


def markdown_table_cell(value: object) -> str:
    text = str(value if value is not None else '')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = ' '.join(line.strip() for line in text.split('\n') if line.strip())
    return text.replace('|', '\\|')


def get_script_root() -> Path:
    return Path(__file__).resolve().parent


def get_default_project_root(script_root: Path) -> Path:
    return script_root.parent.parent


def find_default_site_packages(root: Path) -> Path | None:
    candidates = [
        root / 'runtime' / 'Lib' / 'site-packages',
        root / 'python' / 'Lib' / 'site-packages',
        root / '.venv' / 'Lib' / 'site-packages',
        root / 'venv' / 'Lib' / 'site-packages',
        root / 'runtime' / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages',
        root / '.venv' / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages',
        root / 'venv' / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages',
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


@dataclass
class Record:
    name: str
    version: str
    license: str
    source: str
    license_files: list[Path]


def parse_metadata_text(text: str) -> tuple[str, str, str]:
    msg = Parser().parsestr(text)
    name = (msg.get('Name') or '').strip()
    version = (msg.get('Version') or '').strip()
    lic_expr = (msg.get('License-Expression') or '').strip()
    lic = (msg.get('License') or '').strip()
    if lic == 'UNKNOWN' or '\n' in lic or '\r' in lic or len(lic) > 120:
        lic = ''
    classifiers = [v.strip() for v in msg.get_all('Classifier', []) if v.startswith('License :: ')]
    license_summary = lic_expr or lic or ('; '.join(dict.fromkeys(classifiers)) if classifiers else 'UNKNOWN')
    return name, version, license_summary


def should_include_package(name: str, excluded: set[str]) -> bool:
    return normalize_package_name(name) not in excluded


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_text_hash_from_bytes(data: bytes) -> str:
    try:
        text = data.decode('utf-8-sig')
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = '\n'.join(line.rstrip() for line in text.split('\n')).strip() + '\n'
        payload = text.encode('utf-8')
    except UnicodeDecodeError:
        payload = data
    return hashlib.sha256(payload).hexdigest()


def normalize_text_hash(path: Path) -> str:
    return normalize_text_hash_from_bytes(path.read_bytes())


def clean_generated_license_outputs(licenses_root: Path) -> None:
    if not licenses_root.exists():
        return
    for child in licenses_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
            continue
        if child.name in GENERATED_ROOT_FILES:
            try:
                child.unlink(missing_ok=True)
            except PermissionError:
                warn(f"Could not remove generated file before refresh: {child}")
            continue
        if child.name in PRESERVE_ROOT_FILES:
            continue
        # Keep unknown root files by default for safety.


def package_target_folder(target_root: Path, package_name: str, package_version: str) -> Path:
    folder = target_root / f"{normalize_package_name(package_name)}-{package_version}"
    ensure_directory(folder)
    return folder


def candidate_priority(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    rel = path.as_posix().lower()
    if 'license' in name:
        kind = 0
    elif 'copying' in name:
        kind = 1
    elif 'notice' in name:
        kind = 2
    elif 'authors' in name:
        kind = 3
    else:
        kind = 9
    return (kind, len(rel), rel)


def deduplicate_candidate_files(items: Iterable[Path]) -> list[Path]:
    unique_paths: dict[str, Path] = {}
    for item in items:
        if not item.exists() or not item.is_file():
            continue
        resolved_key = str(item.resolve()).lower()
        current = unique_paths.get(resolved_key)
        if current is None or candidate_priority(item) < candidate_priority(current):
            unique_paths[resolved_key] = item

    by_content: dict[str, list[Path]] = {}
    for item in unique_paths.values():
        by_content.setdefault(normalize_text_hash(item), []).append(item)

    selected: list[Path] = []
    for same_content in by_content.values():
        selected.append(sorted(same_content, key=candidate_priority)[0])

    return sorted(selected, key=candidate_priority)


def copy_license_files_to_target(items: Iterable[Path], target_folder: Path) -> list[Path]:
    copied: list[Path] = []
    ensure_directory(target_folder)
    for src in deduplicate_candidate_files(items):
        if not src.exists() or not src.is_file():
            continue
        dest = target_folder / src.name
        suffix = 1
        while dest.exists():
            dest = target_folder / f"{src.stem}_{suffix}{src.suffix}"
            suffix += 1
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


def copy_fallback_license_files(package_name: str, package_version: str, target_root: Path, fallback_root: Path | None) -> list[Path]:
    if not fallback_root or not fallback_root.exists():
        return []
    package_dir = fallback_root / normalize_package_name(package_name)
    if not package_dir.exists():
        return []
    files = [p for p in package_dir.rglob('*') if p.is_file()]
    if not files:
        return []
    return copy_license_files_to_target(files, package_target_folder(target_root, package_name, package_version))


def is_license_like_name(name: str) -> bool:
    return bool(LICENSE_LIKE_RE.search(name.replace('\\', '/')))


def wheel_dist_info_name(name: str) -> str:
    return re.sub(r'[-.]+', '_', normalize_package_name(name))


def candidate_wheel_license_names(package_name: str) -> list[str]:
    prefix = wheel_dist_info_name(package_name)
    return [
        f'{prefix}.dist-info/LICENSE',
        f'{prefix}.dist-info/LICENSE.txt',
        f'{prefix}.dist-info/COPYING',
        f'{prefix}.dist-info/COPYING.txt',
        f'{prefix}.dist-info/NOTICE',
        f'{prefix}.dist-info/NOTICE.txt',
        f'{prefix}.dist-info/AUTHORS',
        f'{prefix}.dist-info/AUTHORS.txt',
    ]


def copy_wheel_license_files(zf: ZipFile, package_name: str, package_version: str, target_root: Path) -> list[Path]:
    target = package_target_folder(target_root, package_name, package_version)
    copied: list[Path] = []
    names = set(zf.namelist())
    candidates = []
    for fn in names:
        if '/.dist-info/licenses/' in f'/{fn}' or DIST_INFO_FILE_RE.search(fn) or is_license_like_name(fn):
            candidates.append(fn)
    for fn in candidate_wheel_license_names(package_name):
        if fn in names:
            candidates.append(fn)
    candidates = list(dict.fromkeys(candidates))
    seen_by_content_hash: set[str] = set()
    for name in candidates:
        try:
            data = zf.read(name)
        except KeyError:
            continue
        filename = Path(name).name
        signature = normalize_text_hash_from_bytes(data)
        if signature in seen_by_content_hash:
            continue
        seen_by_content_hash.add(signature)
        dest = target / filename
        suffix = 1
        while dest.exists():
            dest = target / f"{Path(filename).stem}_{suffix}{Path(filename).suffix}"
            suffix += 1
        dest.write_bytes(data)
        copied.append(dest)
    return copied


def get_wheel_record(wheel_path: Path, target_root: Path, excluded: set[str], fallback_root: Path | None) -> Record | None:
    with ZipFile(wheel_path) as zf:
        metadata_name = next((n for n in zf.namelist() if n.endswith('.dist-info/METADATA')), None)
        if not metadata_name:
            warn(f"METADATA not found in wheel: {wheel_path}")
            return None
        text = zf.read(metadata_name).decode('utf-8', errors='replace')
        name, version, license_summary = parse_metadata_text(text)
        if not name:
            warn(f"Package name not found in wheel metadata: {wheel_path}")
            return None
        if not should_include_package(name, excluded):
            return None
        copied = copy_wheel_license_files(zf, name, version, target_root)
        if not copied:
            copied = copy_fallback_license_files(name, version, target_root, fallback_root)
        return Record(name=name, version=version, license=license_summary, source='wheelhouse', license_files=copied)


def copy_installed_license_files(dist_info_path: Path, package_name: str, package_version: str, target_root: Path) -> list[Path]:
    target = package_target_folder(target_root, package_name, package_version)
    candidates: list[Path] = []
    licenses_dir = dist_info_path / 'licenses'
    if licenses_dir.exists():
        candidates.extend([p for p in licenses_dir.rglob('*') if p.is_file()])
    candidates.extend([p for p in dist_info_path.iterdir() if p.is_file() and is_license_like_name(p.name)])
    return copy_license_files_to_target(candidates, target)


def get_installed_record(dist_info_path: Path, target_root: Path, excluded: set[str], fallback_root: Path | None) -> Record | None:
    metadata_path = dist_info_path / 'METADATA'
    if not metadata_path.exists():
        return None
    text = metadata_path.read_text(encoding='utf-8', errors='replace')
    name, version, license_summary = parse_metadata_text(text)
    if not name or not should_include_package(name, excluded):
        return None
    copied = copy_installed_license_files(dist_info_path, name, version, target_root)
    if not copied:
        copied = copy_fallback_license_files(name, version, target_root, fallback_root)
    return Record(name=name, version=version, license=license_summary, source='site-packages', license_files=copied)


def merge_records(records: Iterable[Record | None], prefer_installed: bool) -> list[Record]:
    merged: dict[tuple[str, str], Record] = {}
    for record in records:
        if not record:
            continue
        key = (normalize_package_name(record.name), record.version)
        current = merged.get(key)
        if current is None:
            merged[key] = record
            continue
        if prefer_installed and record.source == 'site-packages':
            merged[key] = record
            continue
        if current.source == 'site-packages' and not (prefer_installed and record.source == 'wheelhouse'):
            continue
        if len(record.license_files) > len(current.license_files):
            merged[key] = record
    return sorted(merged.values(), key=lambda r: (normalize_package_name(r.name), r.version))


def package_name_set(records: Iterable[Record]) -> set[str]:
    return {normalize_package_name(r.name) for r in records if r.name}


def test_manifest_condition(item: dict, root: Path, package_names: set[str]) -> bool:
    has_condition = False
    for rel in item.get('whenPathExists', []) or []:
        has_condition = True
        if rel and (root / rel).exists():
            return True
    for package_name in item.get('whenPackagePresent', []) or []:
        has_condition = True
        if normalize_package_name(str(package_name)) in package_names:
            return True
    return not has_condition


def copy_extra_manifest_files(manifest_path: Path | None, target_root: Path, root: Path, package_names: set[str]) -> list[Record]:
    if not manifest_path or not manifest_path.exists():
        return []
    manifest_dir = manifest_path.parent
    items = json.loads(manifest_path.read_text(encoding='utf-8'))
    records: list[Record] = []
    for item in items:
        if not test_manifest_condition(item, root, package_names):
            continue
        name = str(item.get('name', ''))
        version = str(item.get('version', ''))
        lic = str(item.get('license', 'UNKNOWN'))
        source = str(item.get('source', 'extra'))
        target = package_target_folder(target_root, name, version)
        copied: list[Path] = []
        for rel_file in item.get('files', []) or []:
            src = manifest_dir / rel_file
            if not src.exists():
                warn(f"Extra license file not found: {src}")
                continue
            copied.extend(copy_license_files_to_target([src], target))
        records.append(Record(name=name, version=version, license=lic, source=source, license_files=copied))
    return records


def record_to_dict(record: Record, project_root: Path) -> dict:
    files: list[str] = []
    for file in record.license_files:
        try:
            files.append(file.relative_to(project_root).as_posix())
        except ValueError:
            files.append(file.as_posix())
    return {
        'name': record.name,
        'version': record.version,
        'license': record.license,
        'source': record.source,
        'license_files': files,
    }


def write_records_json(records: list[Record], records_path: Path, project_root: Path) -> None:
    payload = [record_to_dict(record, project_root) for record in records]
    records_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')


def write_notices(records: list[Record], notice_path: Path, project_root: Path) -> None:
    lines = [
        '# THIRD_PARTY_NOTICES',
        '',
        'This file lists third-party components redistributed with this package.',
        '',
        '| Component | Version | License | Source | License files |',
        '|---|---:|---|---|---|',
    ]
    for record in records:
        file_refs: list[str] = []
        for file in record.license_files:
            try:
                relative = file.relative_to(project_root).as_posix()
            except ValueError:
                relative = file.as_posix()
            file_refs.append(f'`{relative}`')
        files_cell = '<br>'.join(file_refs) if file_refs else 'None found automatically'
        lines.append(
            f'| {markdown_table_cell(record.name)} | {markdown_table_cell(record.version)} | '
            f'{markdown_table_cell(record.license)} | {markdown_table_cell(record.source)} | {files_cell} |'
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
    parser = argparse.ArgumentParser(description='Collect third-party licenses from a portable release package.')
    parser.add_argument('--project-root')
    parser.add_argument('--wheelhouse-dir')
    parser.add_argument('--site-packages-dir')
    parser.add_argument('--output-root')
    parser.add_argument('--exclude-packages', nargs='*', default=[])
    parser.add_argument('--extra-manifest-path')
    parser.add_argument('--prefer-installed-metadata', action='store_true')
    parser.add_argument('--clean-output', action='store_true')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_root = get_script_root()
    project_root = Path(args.project_root).resolve() if args.project_root else get_default_project_root(script_root)
    wheelhouse_dir = Path(args.wheelhouse_dir).resolve() if args.wheelhouse_dir else (project_root / 'wheelhouse')
    site_packages_dir = Path(args.site_packages_dir).resolve() if args.site_packages_dir else find_default_site_packages(project_root)
    output_root = Path(args.output_root).resolve() if args.output_root else project_root
    extra_manifest_path = Path(args.extra_manifest_path).resolve() if args.extra_manifest_path else (script_root / 'manifest.json')
    fallback_root = script_root / 'fallbacks'
    licenses_root = output_root / 'licenses'
    notice_path = licenses_root / 'THIRD_PARTY_NOTICES.md'
    records_path = licenses_root / '_records.json'
    excluded = {normalize_package_name(x) for x in args.exclude_packages}

    ensure_directory(licenses_root)
    if args.clean_output:
        clean_generated_license_outputs(licenses_root)

    info(f'Project root : {project_root}')
    info(f'Output root  : {output_root}')
    info(f'Wheelhouse   : {wheelhouse_dir if wheelhouse_dir.exists() else "not found"}')
    info(f'Site-packages: {site_packages_dir if site_packages_dir and site_packages_dir.exists() else "not found"}')
    info(f'Fallbacks    : {fallback_root if fallback_root.exists() else "not found"}')

    records: list[Record] = []
    if wheelhouse_dir.exists():
        for wheel in sorted(wheelhouse_dir.glob('*.whl')):
            record = get_wheel_record(wheel, licenses_root, excluded, fallback_root)
            if record:
                records.append(record)
    if site_packages_dir and site_packages_dir.exists():
        for dist_info in sorted([p for p in site_packages_dir.iterdir() if p.is_dir() and p.name.endswith('.dist-info')], key=lambda p: p.name.lower()):
            record = get_installed_record(dist_info, licenses_root, excluded, fallback_root)
            if record:
                records.append(record)
    package_names = package_name_set(records)
    records.extend(copy_extra_manifest_files(extra_manifest_path, licenses_root, project_root, package_names))
    merged = merge_records(records, args.prefer_installed_metadata)
    write_records_json(merged, records_path, project_root)
    write_notices(merged, notice_path, project_root)
    info(f'Generated: {notice_path}')
    info(f'Generated: {licenses_root}')
    info(f'Components: {len(merged)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
