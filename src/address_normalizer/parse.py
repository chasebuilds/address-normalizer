"""Parse one US mailing address into fields and write it in USPS Publication 28 style."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from address_normalizer.tables import (
    DIRECTIONALS,
    STATE_CODES,
    STATES,
    SUFFIXES,
    UNITS,
    ZIP_FIRST_DIGIT,
)

_ZIP_RE = re.compile(r"^(\d{3,5})(?:-(\d{4}))?$")
_ZIP9_RE = re.compile(r"^\d{8,9}$")
_NUMBER_RE = re.compile(r"^\d+[A-Z]?$|^\d+-\d+$")
_GLUED_UNIT_RE = re.compile(r"^(APT|UNIT|STE|RM|LOT|BLDG|SPC)(\d+[A-Z]?)$")
_PO_BOX_HEADS = (("POST", "OFFICE", "BOX"), ("P", "O", "BOX"), ("PO", "BOX"), ("POBOX",), ("POB",))

FIELDS = (
    "number", "predir", "street_name", "suffix", "postdir", "unit_type", "unit_id",
    "po_box", "city", "state", "zip5", "zip4",
)


@dataclass
class Change:
    rule: str
    before: str
    after: str


@dataclass
class Address:
    raw: str
    number: str = ""
    predir: str = ""
    street_name: str = ""
    suffix: str = ""
    postdir: str = ""
    unit_type: str = ""
    unit_id: str = ""
    po_box: str = ""
    city: str = ""
    state: str = ""
    zip5: str = ""
    zip4: str = ""
    issues: list[str] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def zip(self) -> str:
        return f"{self.zip5}-{self.zip4}" if self.zip4 else self.zip5

    @property
    def line1(self) -> str:
        if self.po_box:
            return f"PO BOX {self.po_box}"
        parts = [self.number, self.predir, self.street_name, self.suffix, self.postdir,
                 self.unit_type, self.unit_id]
        return " ".join(p for p in parts if p)

    @property
    def standardized(self) -> str:
        last = " ".join(p for p in (self.state, self.zip) if p)
        return ", ".join(p for p in (self.line1, self.city, last) if p)

    @property
    def key(self) -> str:
        """Match key for duplicates. The unit designator is left out: APT 4 and # 4 match."""
        place = self.zip5 or f"{self.city}|{self.state}"
        return "|".join([self.number, self.predir, self.street_name, self.suffix,
                         self.postdir, self.unit_id, self.po_box, place])

    def fields(self) -> dict[str, str]:
        return {name: str(getattr(self, name)) for name in FIELDS}


@dataclass
class _Tok:
    text: str  # as written, punctuation removed
    seg: int  # comma-separated segment it came from

    @property
    def up(self) -> str:
        return self.text.upper()


def _tokenize(raw: str, addr: Address) -> list[_Tok]:
    text = raw.replace(" ", " ")
    if re.search(r"\s{2,}", text) or text != text.strip():
        addr.changes.append(Change("spacing", raw, "single spaces"))
    if "." in text:
        addr.changes.append(Change("punctuation", raw, "periods removed"))
    text = text.replace(".", "")
    text = re.sub(r"#\s*", " # ", text)
    toks = [
        _Tok(word, seg)
        for seg, part in enumerate(text.split(","))
        for word in part.split()
    ]
    if any(t.text != t.up for t in toks):
        addr.changes.append(Change("case", raw, "upper case"))
    return toks


def _take_zip(toks: list[_Tok], addr: Address) -> None:
    if len(toks) >= 2 and re.fullmatch(r"\d{4}", toks[-1].up) and _ZIP_RE.match(toks[-2].up):
        last = toks.pop()
        toks[-1] = _Tok(f"{toks[-1].text}-{last.text}", toks[-1].seg)
    if not toks:
        return
    word = toks[-1].up
    zip5 = zip4 = ""
    if m := _ZIP_RE.match(word):
        zip5, zip4 = m.group(1), m.group(2) or ""
    elif _ZIP9_RE.match(word):
        zip5, zip4 = word[:-4], word[-4:]
    else:
        return
    if len(toks) == 1:
        return
    toks.pop()
    padded = zip5.zfill(5)
    if padded != zip5:
        addr.changes.append(Change("zip", zip5, f"{padded} (leading zero restored)"))
    if zip4 and f"{padded}-{zip4}" != word:
        addr.changes.append(Change("zip", word, f"{padded}-{zip4}"))
    addr.zip5, addr.zip4 = padded, zip4


def _take_state(toks: list[_Tok], addr: Address) -> None:
    for n in (4, 3, 2, 1):
        if len(toks) <= n:
            continue
        words = toks[-n:]
        name = " ".join(t.up for t in words)
        code = STATES.get(name) or (name if n == 1 and name in STATE_CODES else "")
        if code:
            del toks[-n:]
            written = " ".join(t.text for t in words)
            if written.upper() != code:
                addr.changes.append(Change("state", written, code))
            addr.state = code
            return


def _po_box(toks: list[_Tok]) -> tuple[int, str] | None:
    ups = [t.up for t in toks]
    for head in _PO_BOX_HEADS:
        n = len(head)
        if tuple(ups[:n]) == head and len(ups) > n:
            return n + 1, toks[n].up
    return None


def _split_no_commas(toks: list[_Tok]) -> tuple[int, str]:
    """Index where the street ends, or -1 with a reason."""
    if box := _po_box(toks):
        return box[0], ""
    for i in range(2, len(toks) - 1):
        if toks[i].up in UNITS:
            return i + 2, ""
        if _GLUED_UNIT_RE.match(toks[i].up):
            return i + 1, ""
    candidates = []
    for j in range(2, len(toks) - 1):
        if toks[j].up in SUFFIXES:
            end = j + 1
            nxt = toks[end].up
            if nxt in DIRECTIONALS and len(nxt) <= 2 and end + 1 < len(toks):
                end += 1
            candidates.append(end)
    if not candidates:
        return -1, "could not tell where the street ends and the city starts (add commas)"
    if len(candidates) > 1:
        return -1, "street and city could be split more than one way (add commas)"
    return candidates[0], ""


def _note(addr: Address, rule: str, written: str, out: str) -> None:
    if written.upper() != out:
        addr.changes.append(Change(rule, written, out))


def _parse_street(toks: list[_Tok], addr: Address) -> None:
    if not toks:
        addr.issues.append("no street line")
        return
    if box := _po_box(toks):
        end, number = box
        written = " ".join(t.text for t in toks[:end])
        addr.po_box = number
        _note(addr, "po_box", written, f"PO BOX {number}")
        if end < len(toks):
            rest = " ".join(t.text for t in toks[end:])
            addr.issues.append(f"unexpected text after PO box: {rest}")
        return
    if not _NUMBER_RE.match(toks[0].up):
        addr.issues.append("no house number")
        return
    addr.number = toks[0].up
    body = toks[1:]
    for i, t in enumerate(body):
        if i == 0:
            continue
        if m := _GLUED_UNIT_RE.match(t.up):
            addr.unit_type, addr.unit_id = UNITS[m.group(1)], m.group(2)
            _note(addr, "unit", t.text, f"{addr.unit_type} {addr.unit_id}")
            extra, body = body[i + 1:], body[:i]
            break
        if t.up in UNITS and i + 1 < len(body):
            addr.unit_type, addr.unit_id = UNITS[t.up], body[i + 1].up.lstrip("#")
            _note(addr, "unit", t.text, addr.unit_type)
            extra, body = body[i + 2:], body[:i]
            break
    else:
        extra = []
    if extra:
        addr.issues.append(f"unexpected text after unit: {' '.join(t.text for t in extra)}")
    words = [t.up for t in body]
    if len(words) >= 3 and words[-1] in DIRECTIONALS and words[-2] in SUFFIXES:
        addr.postdir = DIRECTIONALS[words[-1]]
        _note(addr, "directional", body[-1].text, addr.postdir)
        words, body = words[:-1], body[:-1]
    if len(words) >= 2 and words[-1] in SUFFIXES:
        addr.suffix = SUFFIXES[words[-1]]
        _note(addr, "suffix", body[-1].text, addr.suffix)
        words = words[:-1]
    if len(words) >= 2 and words[0] in DIRECTIONALS:
        addr.predir = DIRECTIONALS[words[0]]
        _note(addr, "directional", body[0].text, addr.predir)
        words = words[1:]
    if not words:
        addr.issues.append("no street name")
    addr.street_name = " ".join(words)


def parse(raw: str) -> Address:
    """Parse one single-line address. Problems go in `issues`, never raise."""
    addr = Address(raw=raw)
    if not raw or not raw.strip():
        addr.issues.append("empty address")
        return addr
    toks = _tokenize(raw, addr)
    _take_zip(toks, addr)
    _take_state(toks, addr)
    if not addr.zip5:
        addr.issues.append("no ZIP code")
    if not addr.state:
        addr.issues.append("no state")
    elif addr.zip5 and ZIP_FIRST_DIGIT.get(addr.state, addr.zip5[0]) != addr.zip5[0]:
        addr.issues.append(f"ZIP {addr.zip5} does not belong to {addr.state}")
    segs = sorted({t.seg for t in toks})
    if len(segs) >= 2:
        street = [t for t in toks if t.seg != segs[-1]]
        city = [t for t in toks if t.seg == segs[-1]]
    else:
        cut, reason = _split_no_commas(toks)
        if cut < 0:
            addr.issues.append(reason)
            return addr
        street, city = toks[:cut], toks[cut:]
    if not city:
        addr.issues.append("no city")
    addr.city = " ".join(t.up for t in city)
    _parse_street(street, addr)
    return addr


def parse_parts(street: str, city: str, state: str, zip_code: str) -> Address:
    """Parse an address held in separate columns."""
    raw = ", ".join(p.strip() for p in (street, city, f"{state} {zip_code}".strip()) if p.strip())
    return parse(raw)
