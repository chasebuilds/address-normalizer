# Benchmark

Written by `benchmark/run_benchmark.py` on 2026-11-21 from a real run.
No number on this page was typed by hand.

Command: `python -m benchmark.run_benchmark --seed 20261121 --places 5000`
Python 3.11.15 on Windows.
Parsing all 8,632 rows took 0.15 s.

## Method

1. Invent 5,000 fake addresses: made-up street and city names, real state codes, ZIPs
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

| Measure | Result |
|---|---:|
| Rows (messy copies of 5,000 fake addresses, plus broken rows) | 8,632 |
| Cleaned rows with every field right | **99.5%** (8,294 of 8,332) |
| Parseable rows with every field right (review counts as wrong) | **98.7%** |
| Duplicate pairs found (recall) | **97.8%** (4,421 of 4,520) |
| Duplicate pairs that were right (precision) | **100.0%** (4,421 of 4,421) |
| All rows sent to review | 3.5% (300) |
| Parseable rows sent to review | 0.8% (68) |
| Broken rows sent to review | 100.0% (232 of 232) |

## Accuracy by field

Share of the 8,400 parseable rows where the field is right. A row sent to review counts as
wrong for every field.

| Field | Right | Accuracy |
|---|---:|---:|
| number | 8,332 | 99.2% |
| predir | 8,332 | 99.2% |
| street_name | 8,332 | 99.2% |
| suffix | 8,332 | 99.2% |
| postdir | 8,294 | 98.7% |
| unit_id | 8,332 | 99.2% |
| po_box | 8,332 | 99.2% |
| city | 8,294 | 98.7% |
| state | 8,332 | 99.2% |
| zip5 | 8,332 | 99.2% |
| zip4 | 8,332 | 99.2% |

## Why parseable rows went to review

| Reason | Rows |
|---|---:|
| street and city could be split more than one way (add commas) | 68 |

## What this does not show

The data is generated, so it only has the kinds of mess the generator writes. Real files have
others: misspelled street names, missing suffixes, rural routes, military addresses, two
addresses in one cell. See [LIMITATIONS.md](LIMITATIONS.md).
