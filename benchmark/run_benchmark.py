"""Score the parser on generated messy addresses and write BENCHMARK.md and the README table."""

from __future__ import annotations

import argparse
import datetime as dt
import platform
import re
import time
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from address_normalizer.clean import find_duplicates
from address_normalizer.parse import parse
from benchmark.generate import generate

SCORED = ["number", "predir", "street_name", "suffix", "postdir", "unit_id", "po_box", "city",
          "state", "zip5", "zip4"]
ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Score:
    places: int
    rows: int
    good: int
    bad: int
    cleaned: int
    exact: int
    fields: dict[str, int]
    review_all: int
    review_good: int
    review_bad: int
    pairs_true: int
    pairs_pred: int
    pairs_hit: int
    reasons: Counter[str]
    seconds: float


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def score(seed: int, places: int) -> Score:
    rows = generate(seed, places)
    start = time.perf_counter()
    addrs = [parse(r["address"]) for r in rows]
    seconds = time.perf_counter() - start
    good = [i for i, r in enumerate(rows) if r["expect"] == "ok"]
    bad = [i for i, r in enumerate(rows) if r["expect"] == "review"]
    cleaned = [i for i in good if addrs[i].ok]

    def right(i: int, f: str) -> bool:
        return addrs[i].ok and addrs[i].fields()[f] == rows[i][f"true_{f}"]

    pred = {frozenset(p) for g in find_duplicates(addrs) for p in combinations(g, 2)}
    by_place: dict[str, list[int]] = {}
    for i in good:
        by_place.setdefault(rows[i]["place"], []).append(i)
    true = {frozenset(p) for g in by_place.values() for p in combinations(g, 2)}
    reasons = Counter(re.sub(r"ZIP \d+ .*", "ZIP does not match state", issue)
                      for i in good if not addrs[i].ok for issue in addrs[i].issues)
    return Score(
        places=places, rows=len(rows), good=len(good), bad=len(bad), cleaned=len(cleaned),
        exact=sum(all(right(i, f) for f in SCORED) for i in cleaned),
        fields={f: sum(right(i, f) for i in good) for f in SCORED},
        review_all=sum(not a.ok for a in addrs), review_good=len(good) - len(cleaned),
        review_bad=sum(not addrs[i].ok for i in bad),
        pairs_true=len(true), pairs_pred=len(pred), pairs_hit=len(true & pred),
        reasons=reasons, seconds=seconds,
    )


def summary_table(s: Score) -> str:
    return "\n".join([
        "| Measure | Result |",
        "|---|---:|",
        f"| Rows (messy copies of {s.places:,} fake addresses, plus broken rows) | {s.rows:,} |",
        f"| Cleaned rows with every field right | **{pct(s.exact, s.cleaned)}** "
        f"({s.exact:,} of {s.cleaned:,}) |",
        f"| Parseable rows with every field right (review counts as wrong) "
        f"| **{pct(s.exact, s.good)}** |",
        f"| Duplicate pairs found (recall) | **{pct(s.pairs_hit, s.pairs_true)}** "
        f"({s.pairs_hit:,} of {s.pairs_true:,}) |",
        f"| Duplicate pairs that were right (precision) | **{pct(s.pairs_hit, s.pairs_pred)}** "
        f"({s.pairs_hit:,} of {s.pairs_pred:,}) |",
        f"| All rows sent to review | {pct(s.review_all, s.rows)} ({s.review_all:,}) |",
        f"| Parseable rows sent to review | {pct(s.review_good, s.good)} ({s.review_good:,}) |",
        f"| Broken rows sent to review | {pct(s.review_bad, s.bad)} "
        f"({s.review_bad} of {s.bad}) |",
    ])


def field_table(s: Score) -> str:
    rows = ["| Field | Right | Accuracy |", "|---|---:|---:|"]
    rows += [f"| {f} | {s.fields[f]:,} | {pct(s.fields[f], s.good)} |" for f in SCORED]
    return "\n".join(rows)


def render(s: Score, seed: int) -> str:
    reason_rows = "\n".join(f"| {r} | {n} |" for r, n in s.reasons.most_common()) or "| none | 0 |"
    return f"""# Benchmark

Written by `benchmark/run_benchmark.py` on {dt.date.today().isoformat()} from a real run.
No number on this page was typed by hand.

Command: `python -m benchmark.run_benchmark --seed {seed} --places {s.places}`
Python {platform.python_version()} on {platform.system()}.
Parsing all {s.rows:,} rows took {s.seconds:.2f} s.

## Method

1. Invent {s.places:,} fake addresses: made-up street and city names, real state codes, ZIPs
   whose first digit fits the state, and the right answer for every field. About 15% are PO boxes
   and about 30% of street addresses have a unit. No real address is used.
2. Write 1 to 3 messy copies of each one. Each copy picks at random: suffix spelled out or
   abbreviated (`Street`, `Str`, `St.`), directionals spelled out, `Apt`/`Apartment`/`#`/`Unit`,
   state as a code, lower-case code or full name, ZIP with its leading zero dropped, ZIP+4 with a
   hyphen, a space or nothing, commas in all, some or none of the places, mixed casing and extra
   spaces.
3. About 5% of the fake addresses are written as broken rows instead (no ZIP, no house number,
   no state, or text like `see attached`). These should go to review.
4. Parse every row. A field counts as right only when the row was cleaned (not sent to review)
   and the field matches the truth exactly. Unit designators are not scored, because a messy copy
   that says `#` cannot tell you whether the truth was `APT` or `UNIT`.
5. Duplicates: every pair of rows that came from the same fake address is a true pair. A pair is
   found when both rows land in the same duplicate group.

## Result

{summary_table(s)}

## Accuracy by field

Share of the {s.good:,} parseable rows where the field is right. A row sent to review counts as
wrong for every field.

{field_table(s)}

## Why parseable rows went to review

| Reason | Rows |
|---|---:|
{reason_rows}

## What this does not show

The data is generated, so it only has the kinds of mess the generator writes. Real files have
others: misspelled street names, missing suffixes, rural routes, military addresses, two
addresses in one cell. See [LIMITATIONS.md](LIMITATIONS.md).
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261121)
    ap.add_argument("--places", type=int, default=5000)
    args = ap.parse_args()
    s = score(args.seed, args.places)
    (ROOT / "BENCHMARK.md").write_text(render(s, args.seed), encoding="utf-8")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"(<!-- benchmark:start -->\r?\n).*?(<!-- benchmark:end -->)",
                  lambda m: m.group(1) + summary_table(s) + "\n" + m.group(2), text, flags=re.S)
    readme.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
    print(summary_table(s))
    print(field_table(s))
    print(s.reasons.most_common())


if __name__ == "__main__":
    main()
