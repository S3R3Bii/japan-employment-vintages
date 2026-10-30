"""Project exact native count cells; never edit or recalculate source workbooks."""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
import zipfile
from decimal import Decimal
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MONTHS = [
    "Jan.",
    "Feb.",
    "Mar.",
    "Apr.",
    "May",
    "June",
    "July",
    "Aug.",
    "Sept.",
    "Oct.",
    "Nov.",
    "Dec.",
]
SHEETS = {"pre2022": "参考 南関東及び近畿地域", "current": "南関東及び近畿地域統計表"}
REGIONS = {"Southern-Kanto": "F", "Kinki": "L"}


def dump(path, obj):
    path.write_bytes((json.dumps(obj, indent=2, ensure_ascii=True) + "\n").encode())


def decode_book(path, sheet):
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            # Phonetic rPh annotations are not part of the displayed Excel cell text.
            strings = [
                "".join(
                    t.text or ""
                    for t in list(n.findall("m:t", NS)) + list(n.findall("m:r/m:t", NS))
                )
                for n in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(
                    "m:si", NS
                )
            ]
        rels = {
            r.attrib["Id"]: r.attrib["Target"]
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        }
        sheets = ET.fromstring(z.read("xl/workbook.xml")).findall(
            "m:sheets/m:sheet", NS
        )
        candidates = [s for s in sheets if s.attrib["name"] == sheet]
        assert len(candidates) == 1
        target = rels[
            candidates[0].attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
        ]
        member = (
            target.lstrip("/")
            if target.startswith("/")
            else str(PurePosixPath("xl") / target)
        )
        cells = {}
        for c in ET.fromstring(z.read(member)).findall(".//m:sheetData/m:row/m:c", NS):
            native_type = c.attrib.get("t", "n")
            v = c.find("m:v", NS)
            token = v.text if v is not None and v.text is not None else ""
            inline = c.find("m:is", NS)
            text = (
                strings[int(token)]
                if native_type == "s" and token
                else (
                    "".join(
                        t.text or ""
                        for t in list(inline.findall("m:t", NS))
                        + list(inline.findall("m:r/m:t", NS))
                    )
                    if native_type == "inlineStr"
                    else token
                )
            )
            cells[c.attrib["r"]] = dict(
                native_type=native_type,
                raw_token=token,
                text=text,
                formula=c.find("m:f", NS) is not None,
            )
        return cells


def period_from_label(label, english_month, previous):
    month = MONTHS.index(english_month) + 1
    label = re.sub(r"\s+", "", unicodedata.normalize("NFKC", label))
    era = re.fullmatch(r"(平成|令和)(元|\d+)年(\d+)月", label)
    greg = re.fullmatch(r"(\d{4})(\d{1,2})", label)
    if era:
        year = (1988 if era[1] == "平成" else 2018) + (
            1 if era[2] == "元" else int(era[2])
        )
        assert int(era[3]) == month
    elif greg:
        year = int(greg[1])
        assert int(greg[2]) == month
    else:
        assert previous is not None and label.isdecimal() and int(label) == month
        year = previous[0] + (month == 1)
    if previous is not None:
        assert (year * 12 + month) - (previous[0] * 12 + previous[1]) == 1
    return year, month


def validate_projection(rows):
    keys = [(r["vintage"], r["region"], r["period"]) for r in rows]
    expected = {
        (v, g, f"{y}-{m:02}")
        for v in SHEETS
        for g in REGIONS
        for y in range(2016, 2022)
        for m in range(1, 13)
    }
    assert len(rows) == len(set(keys)) == 288 and set(keys) == expected
    for r in rows:
        assert (
            r["concept"] == "employed_persons"
            and r["sex"] == "total"
            and r["adjustment"] == "original"
            and r["unit"] == "ten_thousand_persons"
        )
        assert r["native_type"] == "n" and r["formula"] == "false"
        x = Decimal(r["value_token"])
        assert x.is_finite() and x > Decimal("0.5") and x == x.to_integral_value()
    return dict(
        status="PASS_FIXED_COHORT",
        source_count_cells=288,
        periods_per_region_version=72,
        regions=2,
        versions=2,
        missing_keys=0,
        conflicting_keys=0,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=ROOT / "data")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    requests = json.loads((a.private_dir / "requests.json").read_text(encoding="utf-8"))
    assert len(requests) == 2
    rows = []
    bindings = []
    source_receipts = []
    for req in requests:
        path = a.private_dir / req["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == req["sha256"] and req["status"] == 200
        v = req["vintage"]
        cells = decode_book(path, SHEETS[v])
        get = lambda cell: cells.get(cell, {}).get("text", "")
        assert get("F10") == get("L10") == "Employed person"
        assert get("F8") == get("L8") == "就業者"
        assert get("I6") == "Southern-Kanto" and get("O6") == "Kinki"
        unit_cell = "P5" if v == "pre2022" else "E5"
        assert "ten thousand persons" in get(unit_cell)
        title_cell = "F3" if v == "pre2022" else "E2"
        assert "Monthly result in Southern-Kanto and Kinki" in get(title_cell)
        if v == "pre2022":
            assert "Original series" in get("F4") and "before 2020-Census" in get("F4")
        for c in ["F8", "L8", "F10", "L10", "I6", "O6", unit_cell, title_cell] + (
            ["F4"] if v == "pre2022" else []
        ):
            bindings.append(dict(vintage=v, sheet=SHEETS[v], cell=c, text=get(c)))
        previous = None
        for r in range(12, 500):
            en = get(f"C{r}")
            if en not in MONTHS:
                continue
            previous = period_from_label(get(f"B{r}"), en, previous)
            year, month = previous
            if not 2016 <= year <= 2021:
                continue
            for region, col in REGIONS.items():
                cell = f"{col}{r}"
                c = cells[cell]
                rows.append(
                    dict(
                        vintage=v,
                        region=region,
                        period=f"{year}-{month:02}",
                        concept="employed_persons",
                        sex="total",
                        adjustment="original",
                        unit="ten_thousand_persons",
                        value_token=c["raw_token"],
                        native_type=c["native_type"],
                        formula=str(c["formula"]).lower(),
                        source_file=req["file"],
                        source_sha256=digest,
                        sheet=SHEETS[v],
                        cell=cell,
                        period_cell=f"B{r}",
                        period_label=get(f"B{r}"),
                        month_label=en,
                    )
                )
        source_receipts.append(
            {
                k: req[k]
                for k in [
                    "vintage",
                    "file",
                    "url",
                    "started_utc",
                    "completed_utc",
                    "status",
                    "headers",
                    "bytes",
                    "sha256",
                    "protocol_commit",
                    "python",
                    "error",
                ]
            }
        )
    rows.sort(key=lambda r: (r["vintage"], r["region"], r["period"]))
    gate = validate_projection(rows)
    with (a.out / "counts.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    dump(a.out / "header_bindings.json", bindings)
    dump(a.out / "source_receipts.json", source_receipts)
    dump(
        a.out / "input_receipt.json",
        dict(
            gate,
            projection_sha256=hashlib.sha256(
                (a.out / "counts.csv").read_bytes()
            ).hexdigest(),
            source_files=2,
        ),
    )
    print(json.dumps(gate))


if __name__ == "__main__":
    main()
