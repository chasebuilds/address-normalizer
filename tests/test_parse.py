import pytest

from address_normalizer import parse, parse_parts


def rules(raw: str) -> set[str]:
    return {c.rule for c in parse(raw).changes}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("123 Main Street, Springfield, IL 62704", "123 MAIN ST, SPRINGFIELD, IL 62704"),
        ("123 Main Str, Springfield, IL 62704", "123 MAIN ST, SPRINGFIELD, IL 62704"),
        ("9 Oak Avenue, Brookvale, MA 02134", "9 OAK AVE, BROOKVALE, MA 02134"),
        ("9 Oak Boulevard, Brookvale, MA 02134", "9 OAK BLVD, BROOKVALE, MA 02134"),
        ("9 Lark Parkway, Brookvale, MA 02134", "9 LARK PKWY, BROOKVALE, MA 02134"),
    ],
)
def test_suffix_abbreviated(raw: str, expected: str) -> None:
    assert parse(raw).standardized == expected


def test_suffix_word_inside_street_name_is_kept() -> None:
    a = parse("456 Park Lane, Brookvale, MA 02134")
    assert (a.street_name, a.suffix) == ("PARK", "LN")


def test_pre_and_post_directionals() -> None:
    b = parse("5 Southwest 3rd Ave NE, Ovid, TX 75001")
    assert (b.predir, b.street_name, b.suffix, b.postdir) == ("SW", "3RD", "AVE", "NE")


def test_directional_word_as_street_name() -> None:
    a = parse("10 North St, Ashby, MA 01431")
    assert (a.predir, a.street_name, a.suffix) == ("", "NORTH", "ST")


@pytest.mark.parametrize(
    ("raw", "unit_type", "unit_id"),
    [
        ("1 Elm St Apt 4, Ovid, TX 75001", "APT", "4"),
        ("1 Elm St Apartment 4B, Ovid, TX 75001", "APT", "4B"),
        ("1 Elm St #4, Ovid, TX 75001", "#", "4"),
        ("1 Elm St # 4, Ovid, TX 75001", "#", "4"),
        ("1 Elm St Suite 200, Ovid, TX 75001", "STE", "200"),
        ("1 Elm St Unit 7, Ovid, TX 75001", "UNIT", "7"),
        ("1 Elm St Apt12, Ovid, TX 75001", "APT", "12"),
    ],
)
def test_unit_designators(raw: str, unit_type: str, unit_id: str) -> None:
    a = parse(raw)
    assert a.ok
    assert (a.unit_type, a.unit_id, a.suffix) == (unit_type, unit_id, "ST")


def test_unit_on_its_own_comma_segment() -> None:
    a = parse("1 Elm St, Apt 4, Ovid, TX 75001")
    assert (a.unit_id, a.city) == ("4", "OVID")


@pytest.mark.parametrize(
    ("raw", "zip5", "zip4"),
    [
        ("1 Elm St, Ovid, MA 2134", "02134", ""),
        ("1 Elm St, Ovid, MA 02134-0012", "02134", "0012"),
        ("1 Elm St, Ovid, MA 021340012", "02134", "0012"),
        ("1 Elm St, Ovid, MA 21340012", "02134", "0012"),
        ("1 Elm St, Ovid, MA 02134 0012", "02134", "0012"),
        ("1 Elm St, Ovid, NY 501", "00501", ""),
    ],
)
def test_zip_formats(raw: str, zip5: str, zip4: str) -> None:
    a = parse(raw)
    assert (a.zip5, a.zip4) == (zip5, zip4)


def test_zip_padding_is_logged() -> None:
    assert "zip" in rules("1 Elm St, Ovid, MA 2134")


@pytest.mark.parametrize(
    ("raw", "state"),
    [
        ("1 Elm St, Ovid, Illinois 62704", "IL"),
        ("1 Elm St, Ovid, west virginia 25301", "WV"),
        ("1 Elm St, Ovid, Virginia 22301", "VA"),
        ("1 Elm St, Ovid, District of Columbia 20001", "DC"),
        ("1 Elm St, Ovid, il 62704", "IL"),
    ],
)
def test_state_names_to_codes(raw: str, state: str) -> None:
    a = parse(raw)
    assert a.ok and a.state == state


def test_zip_state_mismatch_goes_to_review() -> None:
    a = parse("1 Elm St, Ovid, TX 02134")
    assert any("does not belong" in i for i in a.issues)


@pytest.mark.parametrize(
    "raw",
    ["PO Box 77, Ovid, NY 12345", "P.O. Box 77, Ovid, NY 12345",
     "post office box 77, Ovid, NY 12345",
     "POB 77, Ovid, NY 12345", "P O Box 77 Ovid NY 12345"],
)
def test_po_boxes(raw: str) -> None:
    a = parse(raw)
    assert a.ok
    assert a.standardized == "PO BOX 77, OVID, NY 12345"


def test_casing_spacing_punctuation_logged() -> None:
    assert {"case", "spacing", "punctuation"} <= rules("  12  elm st.,  Ovid, TX 75001")
    assert parse("  12  elm st.,  Ovid, TX 75001").standardized == "12 ELM ST, OVID, TX 75001"


def test_clean_address_has_no_changes() -> None:
    assert parse("12 ELM ST, OVID, TX 75001").changes == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12 Elm St Ovid TX 75001", "12 ELM ST, OVID, TX 75001"),
        ("12 Elm St Apt 3 Cedar Falls IA 50613", "12 ELM ST APT 3, CEDAR FALLS, IA 50613"),
        ("12 W Elm Rd SE Ovid TX 75001", "12 W ELM RD SE, OVID, TX 75001"),
        ("PO Box 9 Ovid TX 75001", "PO BOX 9, OVID, TX 75001"),
    ],
)
def test_no_commas(raw: str, expected: str) -> None:
    assert parse(raw).standardized == expected


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("", "empty address"),
        ("12 Elm St, Ovid, TX", "no ZIP code"),
        ("12 Elm St, Ovid, 75001", "no state"),
        ("Elm St, Ovid, TX 75001", "no house number"),
        ("12 Broadway New York NY 10001", "could not tell where the street ends"),
        ("9 Main St Park City UT 84060", "more than one way"),
        ("12 Elm St Apt 4 Rear, Ovid, TX 75001", "unexpected text after unit"),
    ],
)
def test_review_reasons(raw: str, reason: str) -> None:
    a = parse(raw)
    assert not a.ok
    assert any(reason in i for i in a.issues)


def test_separate_columns() -> None:
    a = parse_parts("12 elm street", "ovid", "Texas", "75001")
    assert a.standardized == "12 ELM ST, OVID, TX 75001"


def test_key_ignores_unit_designator() -> None:
    assert parse("1 Elm St Apt 4, Ovid, TX 75001").key == parse("1 elm street #4 Ovid TX 75001").key
