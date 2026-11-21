"""Clean a table of addresses: parse each row, group duplicates, write the workbook."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from address_normalizer.parse import FIELDS, Address, parse, parse_parts

Row = dict[str, str]


@dataclass
class Columns:
    address: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None

    def needed(self) -> list[str]:
        if self.address:
            return [self.address]
        named = [c for c in (self.street, self.city, self.state, self.zip) if c]
        if not self.street:
            raise ValueError("give --column, or --street with --city/--state/--zip")
        return named


@dataclass
class Result:
    headers: list[str]
    rows: list[Row]
    addresses: list[Address]
    groups: list[list[int]]  # row indexes (0-based) that share one normalized address

    @property
    def review(self) -> list[int]:
        return [i for i, a in enumerate(self.addresses) if not a.ok]


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def read_table(path: Path, sheet: str | None = None) -> tuple[list[str], list[Row]]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        values = [[_cell(v) for v in r] for r in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        with path.open(newline="", encoding="utf-8-sig") as f:
            values = list(csv.reader(f))
    if not values:
        return [], []
    headers = [h.strip() for h in values[0]]
    rows = [dict(zip(headers, r + [""] * (len(headers) - len(r)), strict=False))
            for r in values[1:] if any(c.strip() for c in r)]
    return headers, rows


def parse_row(row: Row, cols: Columns) -> Address:
    if cols.address:
        return parse(row[cols.address])
    return parse_parts(*(row.get(c, "") if c else "" for c in
                         (cols.street, cols.city, cols.state, cols.zip)))


def find_duplicates(addresses: list[Address]) -> list[list[int]]:
    by_key: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(addresses):
        if a.ok:
            by_key[a.key].append(i)
    return [rows for rows in by_key.values() if len(rows) > 1]


def clean(headers: list[str], rows: list[Row], cols: Columns) -> Result:
    missing = [c for c in cols.needed() if c not in headers]
    if missing:
        raise ValueError(f"column not found: {', '.join(missing)} (have: {', '.join(headers)})")
    addresses = [parse_row(r, cols) for r in rows]
    return Result(headers, rows, addresses, find_duplicates(addresses))


def _original(row: Row, cols: Columns) -> str:
    return " | ".join(row.get(c, "") for c in cols.needed())


def write_workbook(result: Result, cols: Columns, out: Path) -> None:
    wb = Workbook()
    cleaned = wb.active
    cleaned.title = "Cleaned"
    group_of = {i: g for g, rows in enumerate(result.groups, 1) for i in rows}
    cleaned.append(["row", *result.headers, "standardized", "status", *FIELDS, "duplicate_group"])
    for i, (row, a) in enumerate(zip(result.rows, result.addresses, strict=True)):
        fields = a.fields()
        cleaned.append([i + 2, *(row.get(h, "") for h in result.headers),
                        a.standardized if a.ok else "", "ok" if a.ok else "review",
                        *(fields[f] if a.ok else "" for f in FIELDS), group_of.get(i, "")])

    review = wb.create_sheet("Review")
    review.append(["row", "original", "reason", "best_guess"])
    for i in result.review:
        a = result.addresses[i]
        review.append([i + 2, _original(result.rows[i], cols), "; ".join(a.issues),
                       a.standardized])

    dups = wb.create_sheet("Duplicates")
    dups.append(["group", "row", "original", "standardized"])
    for g, idxs in enumerate(result.groups, 1):
        for i in idxs:
            dups.append([g, i + 2, _original(result.rows[i], cols),
                         result.addresses[i].standardized])

    changes = wb.create_sheet("Changes")
    changes.append(["row", "rule", "before", "after"])
    for i, a in enumerate(result.addresses):
        for c in a.changes:
            changes.append([i + 2, c.rule, c.before, c.after])

    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in col[:200])
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 6), 60)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
