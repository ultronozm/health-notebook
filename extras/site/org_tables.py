"""Small, domain-neutral parser for Org tables and their heading context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OrgTable:
    source: str
    start_line: int
    headings: tuple[str, ...]
    headers: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


def is_separator_row(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and "-" in stripped and set(stripped) <= set("|+- ")


def is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def split_table_line(line: str) -> list[str]:
    return [part.strip() for part in line.strip().strip("|").split("|")]


def parse_org_tables(path: Path, source_root: Path) -> list[OrgTable]:
    """Parse tables in PATH, retaining their enclosing heading hierarchy."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    headings: list[str] = []
    tables: list[OrgTable] = []
    heading_re = re.compile(r"^(\*+)\s+(.*)$")

    i = 0
    while i < len(lines):
        line = lines[i]
        heading_match = heading_re.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            headings = headings[: level - 1] + [heading_match.group(2).strip()]
            i += 1
            continue

        if not is_table_line(line):
            i += 1
            continue

        start_line = i + 1
        raw_rows: list[str] = []
        while i < len(lines) and is_table_line(lines[i]):
            raw_rows.append(lines[i])
            i += 1

        data_rows = [
            split_table_line(raw)
            for raw in raw_rows
            if not is_separator_row(raw)
        ]
        if not data_rows:
            continue

        headers = data_rows[0]
        rows: list[dict[str, str]] = []
        for raw_row in data_rows[1:]:
            padded = raw_row + [""] * max(0, len(headers) - len(raw_row))
            rows.append(
                {
                    header: padded[index].strip()
                    for index, header in enumerate(headers)
                }
            )

        tables.append(
            OrgTable(
                source=str(path.relative_to(source_root)),
                start_line=start_line,
                headings=tuple(headings),
                headers=tuple(headers),
                rows=tuple(rows),
            )
        )

    return tables
