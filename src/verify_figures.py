"""Derive values and transformed geometry from source exports, independently of plotting."""

import csv, hashlib, json, re
from fractions import Fraction as F
from pathlib import Path
from xml.etree import ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
SVG = "{http://www.w3.org/2000/svg}"


def read(p):
    return list(csv.DictReader((ROOT / p).open(encoding="utf-8")))


def vertices(node):
    p = node.find(".//" + SVG + "path")
    assert p is not None
    nums = [
        float(x)
        for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", p.attrib["d"])
    ]
    assert len(nums) % 2 == 0
    pts = list(zip(nums[::2], nums[1::2]))
    return pts[:-1] if pts[0] == pts[-1] else pts


def main():
    levels = read("results/development/levels.csv") + read("results/later/levels.csv")
    growth = read("results/later/growth.csv")
    look = {(r["region"], r["period"], r["method"]): F(r["growth"]) for r in growth}
    summary = next(
        r
        for r in read("results/later/summary.csv")
        if r["region"] == "All" and r["comparison"] == "mixed_vs_current"
    )
    maps = json.loads((ROOT / "figures/value_map.json").read_text(encoding="utf-8"))
    vc = cc = hc = 0
    for fig in maps:
        tree = E.parse(ROOT / "figures" / (fig["figure"] + ".svg"))
        ids = {n.get("id"): n for n in tree.iter() if n.get("id")}
        areas = []
        for i, limits in enumerate(fig["axes"]):
            area = vertices(ids[f"data-area-{i}"])
            areas.append(
                (
                    min(x for x, y in area),
                    max(x for x, y in area),
                    min(y for x, y in area),
                    max(y for x, y in area),
                )
            )
        for item in fig["items"]:
            kind = item["kind"]
            ai = item["axis"]
            node = ids[item["id"]]
            if kind == "revision_line":
                rows = sorted(
                    [r for r in levels if r["region"] == item["region"]],
                    key=lambda r: r["period"],
                )
                values = [F(r["revision_ten_thousand"]) for r in rows]
                assert [F(v) for v in item["values_exact"]] == values
                vc += len(values)
                expected = list(zip(range(72), map(float, values)))
                actual = vertices(node)
                assert fig["axes"][ai] == dict(xlim=[-1, 72], ylim=[0, 16])
            elif kind == "growth_markers":
                periods = sorted(
                    {r["period"] for r in growth if r["region"] == item["region"]}
                )
                assert item["periods"] == periods
                values = [
                    (
                        look[item["region"], t, "current"],
                        look[item["region"], t, "mixed"],
                    )
                    for t in periods
                ]
                assert [[F(v) for v in pair] for pair in item["values_exact"]] == [
                    list(v) for v in values
                ]
                vc += 2 * len(values)
                expected = [(100 * float(x), 100 * float(y)) for x, y in values]
                actual = [
                    (float(n.attrib["x"]), float(n.attrib["y"]))
                    for n in node.findall(".//" + SVG + "use")
                ]
                assert fig["axes"][ai] == dict(xlim=[-2.5, 3.7], ylim=[-2.5, 3.7])
            else:
                suffix = item["suffix"]
                index = ["005", "010"].index(suffix)
                if kind == "error_bar":
                    value = int(summary[item["field"]])
                    x = index + (-0.18 if item["field"].startswith("point") else 0.18)
                    width = 0.30
                    bottom = 0
                    assert ai == 0
                else:
                    assert kind == "coverage_bar"
                    both = int(summary["both_certified_" + suffix])
                    value = both if item["field"] == "both" else 72 - both
                    x = index
                    width = 0.58
                    bottom = 0 if item["field"] == "both" else both
                    assert ai == 1
                assert F(item["value_exact"]) == value
                assert (
                    item["x"] == x
                    and item["width"] == width
                    and item["bottom"] == bottom
                )
                vc += 1
                expected = [
                    (x - width / 2, bottom),
                    (x + width / 2, bottom),
                    (x + width / 2, bottom + value),
                    (x - width / 2, bottom + value),
                ]
                actual = vertices(node)
                assert fig["axes"][ai] == dict(
                    xlim=[-0.6, 1.6], ylim=[0, 16 if ai == 0 else 80]
                )
            left, right, top, bottom = areas[ai]
            xmin, xmax = fig["axes"][ai]["xlim"]
            ymin, ymax = fig["axes"][ai]["ylim"]
            mapped = [
                (
                    left + (x - xmin) / (xmax - xmin) * (right - left),
                    bottom - (y - ymin) / (ymax - ymin) * (bottom - top),
                )
                for x, y in expected
            ]
            assert len(actual) == len(mapped), (item["id"], len(actual), len(mapped))
            for a, b in zip(actual, mapped):
                assert max(abs(x - y) for x, y in zip(a, b)) < 0.00002, (
                    item["id"],
                    a,
                    b,
                )
                cc += 2
        for path, digest in fig["files"].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
            hc += 1
    result = dict(
        status="PASS_SOURCE_VALUES_AND_ACTUAL_SVG_GEOMETRY",
        figures=3,
        value_checks=vc,
        coordinate_checks=cc,
        export_hash_checks=hc,
    )
    (ROOT / "figures/verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
