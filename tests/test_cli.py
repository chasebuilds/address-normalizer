import csv
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from address_normalizer.cli import main

ROWS = [
    ("1", "123 Main Street Apt 4, Ovid, Texas 75001"),
    ("2", "123 main st #4 Ovid TX 75001"),
    ("3", "PO Box 9, Ashby, MA 1431"),
    ("4", "not an address"),
]


def write_csv(path: Path) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "address"])
        w.writerows(ROWS)
    return path


def sheet(path: Path, name: str) -> list[tuple[object, ...]]:
    return list(load_workbook(path)[name].iter_rows(values_only=True))


def test_clean_csv_writes_four_sheets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out.xlsx"
    assert main(["clean", str(write_csv(tmp_path / "in.csv")), "--column", "address",
                 "-o", str(out)]) == 0
    assert load_workbook(out).sheetnames == ["Cleaned", "Review", "Duplicates", "Changes"]
    cleaned = sheet(out, "Cleaned")
    header = cleaned[0]
    std = header.index("standardized")
    assert cleaned[1][std] == "123 MAIN ST APT 4, OVID, TX 75001"
    assert cleaned[3][std] == "PO BOX 9, ASHBY, MA 01431"
    assert cleaned[4][header.index("status")] == "review"
    review = sheet(out, "Review")
    assert len(review) == 2 and review[1][0] == 5
    dups = sheet(out, "Duplicates")
    assert [r[1] for r in dups[1:]] == [2, 3]
    changes = sheet(out, "Changes")
    assert ("state" in {r[1] for r in changes}) and ("zip" in {r[1] for r in changes})
    printed = capsys.readouterr().out
    assert "3 cleaned, 1 sent to review" in printed
    assert "1 duplicate groups covering 2 rows" in printed


def test_clean_excel_with_split_columns(tmp_path: Path) -> None:
    src = tmp_path / "in.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["street", "city", "state", "zip"])
    ws.append(["12 elm street", "Ovid", "Texas", 75001])
    ws.append(["4 Oak Ave", "Ashby", "massachusetts", 1431])
    wb.save(src)
    out = tmp_path / "out.xlsx"
    assert main(["clean", str(src), "--street", "street", "--city", "city", "--state", "state",
                 "--zip", "zip", "-o", str(out)]) == 0
    cleaned = sheet(out, "Cleaned")
    std = cleaned[0].index("standardized")
    assert [r[std] for r in cleaned[1:]] == ["12 ELM ST, OVID, TX 75001",
                                             "4 OAK AVE, ASHBY, MA 01431"]


def test_missing_column_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["clean", str(write_csv(tmp_path / "in.csv")), "--column", "addr",
                 "-o", str(tmp_path / "o.xlsx")]) == 2
    assert "column not found: addr" in capsys.readouterr().err


def test_no_column_option_exits_2(tmp_path: Path) -> None:
    assert main(["clean", str(write_csv(tmp_path / "in.csv")), "-o", str(tmp_path / "o.xlsx")]) == 2


def test_missing_file_exits_2(tmp_path: Path) -> None:
    assert main(["clean", str(tmp_path / "nope.csv"), "--column", "a"]) == 2
