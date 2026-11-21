"""Generate fake US addresses with known truth, then messy copies of them.

Street and city names are invented from syllables. State codes are real and ZIPs start with the
right first digit for the state, so they look plausible, but no row is a real address.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
from pathlib import Path

from address_normalizer.parse import FIELDS
from address_normalizer.tables import STATES, ZIP_FIRST_DIGIT

HEADS = ["Bram", "Cor", "Dell", "Fen", "Gar", "Hal", "Kes", "Lor", "Mar", "Nor", "Ost", "Pell",
         "Quin", "Ros", "Tav", "Vel", "Wex", "Yar", "Ash", "Brin", "Cal", "Dun", "Elm", "Har"]
TAILS = ["wick", "ford", "ley", "mont", "stead", "by", "ton", "more", "dale", "holt", "wyn",
         "bury", "ham", "worth", "cote", "sley"]
SUFFIX_FORMS = {
    "ST": ["Street", "St", "Str", "St."], "AVE": ["Avenue", "Ave", "Av", "Ave."],
    "RD": ["Road", "Rd", "Rd."], "DR": ["Drive", "Dr", "Drv"], "LN": ["Lane", "Ln"],
    "CT": ["Court", "Ct", "Crt"], "BLVD": ["Boulevard", "Blvd", "Boul"], "PL": ["Place", "Pl"],
    "WAY": ["Way"], "CIR": ["Circle", "Cir", "Circ"], "TER": ["Terrace", "Ter", "Terr"],
    "PKWY": ["Parkway", "Pkwy", "Pky"], "TRL": ["Trail", "Trl"], "HWY": ["Highway", "Hwy"],
}
DIRS = {"N": "North", "S": "South", "E": "East", "W": "West", "NE": "Northeast",
        "NW": "Northwest", "SE": "Southeast", "SW": "Southwest"}
UNIT_FORMS = {"APT": ["Apt", "Apartment", "#", "Apt."], "UNIT": ["Unit", "#"],
              "STE": ["Suite", "Ste", "Ste."]}
PO_FORMS = ["PO Box", "P.O. Box", "Post Office Box", "POB", "P O Box", "po box"]
STATE_NAME = {code: name for name, code in STATES.items()}
MAINLAND = sorted(c for c in ZIP_FIRST_DIGIT if c not in {"PR", "VI", "GU", "AS", "MP"})


def _word(rng: random.Random) -> str:
    return rng.choice(HEADS) + rng.choice(TAILS)


def _ordinal(n: int) -> str:
    tail = "TH" if 10 <= n % 100 <= 20 else {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")
    return f"{n}{tail}"


def make_truth(rng: random.Random) -> dict[str, str]:
    t = dict.fromkeys(FIELDS, "")
    if rng.random() < 0.15:
        t["po_box"] = str(rng.randint(1, 9999))
    else:
        t["number"] = str(rng.randint(1, 9999))
        if rng.random() < 0.2:
            t["predir"] = rng.choice(list(DIRS))
        t["street_name"] = _ordinal(rng.randint(1, 60)) if rng.random() < 0.1 else (
            _word(rng).upper())
        t["suffix"] = rng.choice(list(SUFFIX_FORMS))
        if rng.random() < 0.05:
            t["postdir"] = rng.choice(list(DIRS))
        if rng.random() < 0.3:
            t["unit_type"] = rng.choice(list(UNIT_FORMS))
            t["unit_id"] = str(rng.randint(1, 999)) + ("B" if rng.random() < 0.1 else "")
    r = rng.random()
    city = _word(rng)
    if r < 0.05:
        city = f"Lake {city}"
    elif r < 0.12:
        city = f"{city} Falls"
    elif r < 0.17:
        city = f"New {city}"
    t["city"] = city.upper()
    t["state"] = rng.choice(MAINLAND)
    t["zip5"] = ZIP_FIRST_DIGIT[t["state"]] + f"{rng.randint(0, 9999):04d}"
    if rng.random() < 0.25:
        t["zip4"] = f"{rng.randint(1, 9999):04d}"
    return t


def _case(rng: random.Random, text: str) -> str:
    return rng.choice([text.upper(), text.lower(), text.title(), text.title(), text])


def messy(rng: random.Random, t: dict[str, str]) -> str:
    if t["po_box"]:
        street = f"{rng.choice(PO_FORMS)} {t['po_box']}"
    else:
        parts = [t["number"]]
        if t["predir"]:
            d = t["predir"]
            parts.append(rng.choice([d, DIRS[d], d + "."]))
        name = t["street_name"]
        parts.append(name.lower() if name[0].isdigit() and rng.random() < 0.5 else name.title())
        parts.append(rng.choice(SUFFIX_FORMS[t["suffix"]]))
        if t["postdir"]:
            parts.append(rng.choice([t["postdir"], DIRS[t["postdir"]]]))
        if t["unit_type"]:
            form = rng.choice(UNIT_FORMS[t["unit_type"]])
            glue = form == "#" and rng.random() < 0.5
            parts.append(f"#{t['unit_id']}" if glue else f"{form} {t['unit_id']}")
        street = " ".join(parts)
    state = rng.choice([t["state"], t["state"].lower(), STATE_NAME[t["state"]].title(),
                        STATE_NAME[t["state"]]])
    zip5 = t["zip5"].lstrip("0") if t["zip5"].startswith("0") and rng.random() < 0.4 else t["zip5"]
    zip_text = zip5
    if t["zip4"]:
        zip_text += rng.choice(["-", "", " "]) + t["zip4"]
    city = t["city"].title()
    style = rng.random()
    if style < 0.5:
        text = f"{street}, {city}, {state} {zip_text}"
    elif style < 0.75:
        text = f"{street}, {city} {state} {zip_text}"
    else:
        text = f"{street} {city} {state} {zip_text}"
    text = _case(rng, text)
    if rng.random() < 0.3:
        words = text.split(" ")
        i = rng.randrange(len(words))
        words[i] = words[i] + " "
        text = "  " * rng.randint(0, 1) + " ".join(words)
    return text


def broken(rng: random.Random, t: dict[str, str]) -> str:
    good = messy(rng, t)
    kind = rng.randrange(4)
    if kind == 0:
        return re.sub(r"[\s,]*\d[\d\s-]*$", "", good)
    if kind == 1:
        return f"{t['street_name'].title()} {SUFFIX_FORMS[t['suffix'] or 'ST'][0]}, " + (
            f"{t['city'].title()}, {t['state']} {t['zip5']}")
    if kind == 2:
        return rng.choice(["see attached", "same as billing", "N/A", "unknown", ""])
    return f"{t['number'] or '1'} {_word(rng)} {t['city'].title()} {t['zip5']}"


def generate(seed: int, n_places: int, broken_share: float = 0.05) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for place in range(n_places):
        t = make_truth(rng)
        if rng.random() < broken_share:
            rows.append({"id": "", "place": "", "expect": "review", "address": broken(rng, t),
                         **{f"true_{k}": "" for k in FIELDS}})
            continue
        for _ in range(rng.choice([1, 1, 2, 2, 3])):
            rows.append({"id": "", "place": str(place), "expect": "ok",
                         "address": messy(rng, t), **{f"true_{k}": v for k, v in t.items()}})
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["id"] = str(i)
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--places", type=int, default=25)
    ap.add_argument("--out", type=Path, default=Path("samples/messy.csv"))
    args = ap.parse_args()
    write_csv(generate(args.seed, args.places), args.out)


if __name__ == "__main__":
    main()
