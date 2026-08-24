from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".venv_latest",
        "._runtime",
        "__pycache__",
        "data",
        "input",
        "logs",
        "node_modules",
        "output",
        "report",
        "release",
        "runtime",
        "venv",
        "wheelhouse",
        "workspace",
    }
)


@dataclass(frozen=True)
class CmdEncodingResult:
    path: Path
    has_bom: bool
    crlf: int
    lone_lf: int
    lone_cr: int
    valid_utf8: bool
    error: str = ""

    @property
    def ok(self) -> bool:
        return (
            not self.has_bom
            and self.lone_lf == 0
            and self.lone_cr == 0
            and self.valid_utf8
        )

    def summary(self) -> str:
        return (
            f"BOM={self.has_bom} "
            f"CRLF={self.crlf} "
            f"LoneLF={self.lone_lf} "
            f"LoneCR={self.lone_cr} "
            f"UTF8={self.valid_utf8}"
        )


def iter_cmd_files(root: Path) -> list[Path]:
    root = root.resolve()
    found: list[Path] = []
    stack = [root]

    while stack:
        current = stack.pop()
        for child in current.iterdir():
            if child.is_dir():
                if child.name in EXCLUDED_DIR_NAMES:
                    continue
                stack.append(child)
                continue
            if child.is_file() and child.suffix.lower() == ".cmd":
                found.append(child)

    return sorted(found)


def inspect_cmd_file(path: Path) -> CmdEncodingResult:
    data = path.read_bytes()
    has_bom = data.startswith(b"\xef\xbb\xbf")

    crlf = 0
    lone_lf = 0
    lone_cr = 0
    for index, byte in enumerate(data):
        if byte == 0x0A:
            if index > 0 and data[index - 1] == 0x0D:
                crlf += 1
            else:
                lone_lf += 1
        elif byte == 0x0D and (index + 1 >= len(data) or data[index + 1] != 0x0A):
            lone_cr += 1

    offset = 3 if has_bom else 0
    try:
        data[offset:].decode("utf-8")
        valid_utf8 = True
        error = ""
    except UnicodeDecodeError as exc:
        valid_utf8 = False
        error = f"{exc.__class__.__name__}: {exc}"

    return CmdEncodingResult(
        path=path,
        has_bom=has_bom,
        crlf=crlf,
        lone_lf=lone_lf,
        lone_cr=lone_cr,
        valid_utf8=valid_utf8,
        error=error,
    )


def check_cmd_files(root: Path) -> list[CmdEncodingResult]:
    return [inspect_cmd_file(path) for path in iter_cmd_files(root)]


def normalize_cmd_file(path: Path) -> CmdEncodingResult:
    data = path.read_bytes()
    offset = 3 if data.startswith(b"\xef\xbb\xbf") else 0
    text = data[offset:].decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]

    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    path.write_text(text, encoding="utf-8", newline="")
    return inspect_cmd_file(path)


def _format_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that project CMD files are UTF-8 without BOM and CRLF."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Project root. Defaults to the repository root.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Normalize UTF-8 CMD files to no-BOM CRLF.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    results = check_cmd_files(root)
    fixed: list[CmdEncodingResult] = []
    bad: list[CmdEncodingResult] = []

    for result in results:
        if result.ok:
            continue
        if args.fix and result.valid_utf8:
            fixed_result = normalize_cmd_file(result.path)
            fixed.append(fixed_result)
            if not fixed_result.ok:
                bad.append(fixed_result)
            continue
        bad.append(result)

    for result in fixed:
        print(f"[FIXED] {_format_path(result.path, root)} {result.summary()}")

    if bad:
        print("[ERROR] CMD encoding check failed.")
        for result in bad:
            detail = result.summary()
            if result.error:
                detail = f"{detail} {result.error}"
            print(f"  - {_format_path(result.path, root)} {detail}")
        return 1

    print(f"[OK] CMD encoding: {len(results)} file(s) checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
