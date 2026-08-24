from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import re


@dataclass
class TableBlock:
    start_line: int
    end_line: int
    rows: int
    h2: str | None
    h3: str | None


H2_RE = re.compile(r"^##\s+(.*)")
H3_RE = re.compile(r"^###\s+(.*)")


def is_table_line(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False
    if stripped.startswith("|") and stripped.endswith("|"):
        return True
    return False


def inspect_md(path: Path) -> tuple[list[str], list[str], list[TableBlock]]:
    lines = path.read_text(encoding="utf-8").splitlines()

    h2_list: list[str] = []
    h3_list: list[str] = []
    tables: list[TableBlock] = []

    current_h2: str | None = None
    current_h3: str | None = None

    in_table = False
    table_start = 0
    table_rows = 0

    for idx, line in enumerate(lines, start=1):
        h2_match = H2_RE.match(line)
        h3_match = H3_RE.match(line)

        if h2_match:
            current_h2 = h2_match.group(1).strip()
            current_h3 = None
            h2_list.append(current_h2)

        if h3_match:
            current_h3 = h3_match.group(1).strip()
            h3_list.append(current_h3)

        if is_table_line(line):
            if not in_table:
                in_table = True
                table_start = idx
                table_rows = 1
            else:
                table_rows += 1
        else:
            if in_table:
                tables.append(
                    TableBlock(
                        start_line=table_start,
                        end_line=idx - 1,
                        rows=table_rows,
                        h2=current_h2,
                        h3=current_h3,
                    )
                )
                in_table = False
                table_rows = 0

    if in_table:
        tables.append(
            TableBlock(
                start_line=table_start,
                end_line=len(lines),
                rows=table_rows,
                h2=current_h2,
                h3=current_h3,
            )
        )

    return h2_list, h3_list, tables


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect markdown headings and table blocks.")
    parser.add_argument("--input", required=True, help="Path to markdown file")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print("[ERROR] Input file not found:")
        print(path)
        return 1

    h2_list, h3_list, tables = inspect_md(path)

    print("======================================================================")
    print("MARKDOWN TABLE INSPECTOR")
    print("======================================================================")
    print(f"File          : {path}")
    print(f"H2 headings   : {len(h2_list)}")
    print(f"H3 headings   : {len(h3_list)}")
    print(f"Table blocks  : {len(tables)}")
    print()

    if h2_list:
        print("[H2 headings]")
        for item in h2_list[:20]:
            print(f"  - {item}")
        if len(h2_list) > 20:
            print(f"  ... and {len(h2_list) - 20} more")
        print()

    if tables:
        print("[Table blocks]")
        for i, tb in enumerate(tables[:30], start=1):
            print(
                f"  {i:02d}. lines {tb.start_line}-{tb.end_line} | rows={tb.rows} | "
                f"H2={tb.h2 or '-'} | H3={tb.h3 or '-'}"
            )
        if len(tables) > 30:
            print(f"  ... and {len(tables) - 30} more")
    else:
        print("[INFO] No markdown table blocks detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
