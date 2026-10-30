"""Recompute the source-bound display ledger and check the actual six-page PDF."""

import ast, csv, hashlib, json, unicodedata
from fractions import Fraction as F
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return list(csv.DictReader((ROOT / path).open(encoding="utf-8")))


def main():
    pdf = ROOT / "paper/manuscript.pdf"
    reader = PdfReader(pdf)
    assert len(reader.pages) == 6
    pages = [unicodedata.normalize("NFKC", p.extract_text()) for p in reader.pages]
    assert all(len(p) > 900 for p in pages)
    ledger = json.loads(
        (ROOT / "paper/display_ledger.json").read_text(encoding="utf-8")
    )
    checks = 2
    for item in ledger:
        q = item["query"]
        kind = q["kind"]
        if kind == "summary":
            value = F(
                next(
                    r
                    for r in read("results/" + q["phase"] + "/summary.csv")
                    if r["region"] == q["region"] and r["comparison"] == q["comparison"]
                )[q["field"]]
            )
        elif kind == "json":
            value = json.loads((ROOT / q["path"]).read_text(encoding="utf-8"))[
                q["field"]
            ]
        elif kind == "freeze_count":
            value = len(
                json.loads(
                    (ROOT / "data/dependency_freeze.json").read_text(encoding="utf-8")
                )["files"]
            )
        elif kind == "test_count":
            value = sum(
                1
                for p in (ROOT / "tests").glob("test_*.py")
                for node in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
            )
        else:
            assert kind == "example"
            value = (
                F(
                    next(
                        r
                        for r in read("results/later/growth.csv")
                        if r["region"] == q["region"]
                        and r["period"] == q["period"]
                        and r["method"] == q["method"]
                    )[q["field"]]
                )
                * q["multiplier"]
            )
        expected = (
            format(int(value), item["format"])
            if item["format"] == ",d"
            else format(float(value), item["format"])
        )
        assert expected == item["text"]
        assert expected in pages[item["page"]], item
        checks += 2
    text = " ".join(pages).replace("\n", " ")
    for phrase in [
        "authored",
        "not confidence intervals",
        "sampling uncertainty",
        "not a frozen March 2022 release",
        "no analyst-blindness",
        "No parameter is fitted",
        "formal-publication projects excluded",
        "not ground truth",
    ]:
        assert phrase in text, phrase
        checks += 1
    log = (ROOT / "paper/main.log").read_text(encoding="utf-8", errors="replace")
    warnings = [
        l
        for l in log.splitlines()
        if any(
            w in l
            for w in ["Overfull", "Underfull", "Missing character", "Unused global"]
        )
    ]
    assert not warnings, warnings
    checks += 1
    result = dict(
        status="PASS_SOURCE_BOUND_DISPLAYS_AND_PDF_TEXT",
        pages=6,
        displays=len(ledger),
        checks=checks,
        pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        layout_warnings=warnings,
        visual_inspection="Separate recorded human-visible page inspection required",
    )
    (ROOT / "paper/verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
