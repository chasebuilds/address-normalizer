"""Command line: addrnorm clean in.csv --column address -o out.xlsx"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from address_normalizer import __version__
from address_normalizer.clean import Columns, clean, read_table, write_workbook


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="addrnorm", description=__doc__)
    p.add_argument("--version", action="version", version=f"addrnorm {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("clean", help="standardize a CSV or Excel file of addresses")
    c.add_argument("input", type=Path, help="CSV or .xlsx file")
    c.add_argument("--column", help="column holding the whole address on one line")
    c.add_argument("--street", help="street column (with --city, --state, --zip)")
    c.add_argument("--city")
    c.add_argument("--state")
    c.add_argument("--zip")
    c.add_argument("--sheet", help="sheet name for Excel input (default: first)")
    c.add_argument("-o", "--output", type=Path, default=Path("addresses-clean.xlsx"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cols = Columns(args.column, args.street, args.city, args.state, args.zip)
    try:
        headers, rows = read_table(args.input, args.sheet)
        result = clean(headers, rows, cols)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write_workbook(result, cols, args.output)
    n_changes = sum(len(a.changes) for a in result.addresses)
    dup_rows = sum(len(g) for g in result.groups)
    print(f"{len(rows)} rows: {len(rows) - len(result.review)} cleaned, "
          f"{len(result.review)} sent to review")
    print(f"{len(result.groups)} duplicate groups covering {dup_rows} rows, {n_changes} changes")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
