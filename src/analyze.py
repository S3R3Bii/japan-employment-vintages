"""Fixed exact comparisons; no fitted parameters or threshold selection."""

import argparse, csv, hashlib, json, subprocess
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from build_inputs import validate_projection

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = (F(1, 200), F(1, 100))


def sign(x):
    return (x > 0) - (x < 0)


def growth(a, b):
    a, b = F(a), F(b)
    assert a > F(1, 2) and b > F(1, 2)
    return (
        a / b - 1,
        (a - F(1, 2)) / (b + F(1, 2)) - 1,
        (a + F(1, 2)) / (b - F(1, 2)) - 1,
    )


def certified_sign(lo, hi):
    assert lo <= hi
    return "positive" if lo > 0 else ("negative" if hi < 0 else "ambiguous")


def certified_alert(lo, hi, threshold):
    assert lo <= hi and threshold > 0
    if lo >= threshold or hi <= -threshold:
        return "alert"
    if lo > -threshold and hi < threshold:
        return "no_alert"
    return "ambiguous"


def previous_year(period):
    y, m = map(int, period.split("-"))
    assert 1 <= m <= 12
    return f"{y-1}-{m:02}"


def csvout(path, rows):
    assert rows
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(phase, out):
    rows = list(csv.DictReader((ROOT / "data/counts.csv").open(encoding="utf-8")))
    validate_projection(rows)
    index = {
        (r["vintage"], r["region"], r["period"]): F(r["value_token"]) for r in rows
    }
    years = range(2017, 2019) if phase == "development" else range(2019, 2022)
    levels = []
    records = []
    alerts = []
    pairs = []
    for region in ["Southern-Kanto", "Kinki"]:
        levelyears = range(2016, 2019) if phase == "development" else range(2019, 2022)
        for y in levelyears:
            for m in range(1, 13):
                t = f"{y}-{m:02}"
                old = index["pre2022", region, t]
                new = index["current", region, t]
                levels.append(
                    dict(
                        phase=phase,
                        region=region,
                        period=t,
                        old_count=str(old),
                        current_count=str(new),
                        revision_ten_thousand=str(new - old),
                        relative_revision=str(new / old - 1),
                    )
                )
        for y in years:
            for m in range(1, 13):
                t = f"{y}-{m:02}"
                lag = previous_year(t)
                o = index["pre2022", region, t]
                ol = index["pre2022", region, lag]
                n = index["current", region, t]
                nl = index["current", region, lag]
                values = {}
                label = {}
                for method, a, b in [
                    ("archive", o, ol),
                    ("current", n, nl),
                    ("mixed", n, ol),
                ]:
                    point, lo, hi = growth(a, b)
                    s = certified_sign(lo, hi)
                    values[method] = (point, lo, hi, s)
                    records.append(
                        dict(
                            phase=phase,
                            region=region,
                            period=t,
                            lag_period=lag,
                            method=method,
                            numerator=str(a),
                            denominator=str(b),
                            growth=str(point),
                            lower=str(lo),
                            upper=str(hi),
                            point_sign=sign(point),
                            certified_sign=s,
                        )
                    )
                    for threshold in THRESHOLDS:
                        state = certified_alert(lo, hi, threshold)
                        label[method, threshold] = (abs(point) >= threshold, state)
                        alerts.append(
                            dict(
                                phase=phase,
                                region=region,
                                period=t,
                                method=method,
                                threshold=str(threshold),
                                point_alert=int(abs(point) >= threshold),
                                certified_alert=state,
                            )
                        )
                for method in ["archive", "mixed"]:
                    point, lo, hi, s = values[method]
                    reference, rl, rh, rs = values["current"]
                    pair = dict(
                        phase=phase,
                        region=region,
                        period=t,
                        comparison=method + "_vs_current",
                        difference_pp=str(100 * (point - reference)),
                        absolute_difference_pp=str(100 * abs(point - reference)),
                        sign_disagree=int(sign(point) != sign(reference)),
                        strict_opposite=int(point * reference < 0),
                        rounding_robust_opposite=int(
                            s != "ambiguous" and rs != "ambiguous" and s != rs
                        ),
                    )
                    for threshold, suffix in [(F(1, 200), "005"), (F(1, 100), "010")]:
                        a, ac = label[method, threshold]
                        b, bc = label["current", threshold]
                        pair["point_alert_mismatch_" + suffix] = int(a != b)
                        pair["both_certified_" + suffix] = int(
                            ac != "ambiguous" and bc != "ambiguous"
                        )
                        pair["certified_alert_mismatch_" + suffix] = int(
                            ac != "ambiguous" and bc != "ambiguous" and ac != bc
                        )
                    pairs.append(pair)
    groups = defaultdict(list)
    for r in pairs:
        for region in [r["region"], "All"]:
            groups[region, r["comparison"]].append(r)
    summaries = []
    sumfields = [
        k
        for k in pairs[0]
        if k
        not in [
            "phase",
            "region",
            "period",
            "comparison",
            "difference_pp",
            "absolute_difference_pp",
        ]
    ]
    for (region, comparison), group in sorted(groups.items()):
        diff = [F(r["absolute_difference_pp"]) for r in group]
        summary = dict(
            phase=phase,
            region=region,
            comparison=comparison,
            pairs=len(group),
            mean_absolute_difference_pp=str(sum(diff) / len(diff)),
            max_absolute_difference_pp=str(max(diff)),
        )
        summary.update({k: sum(int(r[k]) for r in group) for k in sumfields})
        summaries.append(summary)
    out.mkdir(parents=True, exist_ok=False)
    for name, content in [
        ("levels", levels),
        ("growth", records),
        ("alerts", alerts),
        ("pairs", pairs),
        ("summary", summaries),
    ]:
        csvout(out / (name + ".csv"), content)
    receipt = dict(
        status="PASS_FIXED_DESCRIPTIVE_EXECUTION",
        phase=phase,
        pairs=len(pairs) // 2,
        level_pairs=len(levels),
        growth_rows=len(records),
        alert_rows=len(alerts),
        no_fitting=True,
        source_network=False,
        input_sha256=hashlib.sha256(
            (ROOT / "data/counts.csv").read_bytes()
        ).hexdigest(),
    )
    (out / "execution.json").write_bytes(
        (json.dumps(receipt, indent=2) + "\n").encode()
    )
    print(json.dumps(receipt))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["development", "later"], required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.phase == "later":
        assert (
            subprocess.check_output(
                ["git", "show", "HEAD:data/dependency_freeze.json"], cwd=ROOT
            )
            == (ROOT / "data/dependency_freeze.json").read_bytes()
        ), "Commit the dependency manifest before later summaries"
        manifest = json.loads(
            (ROOT / "data/dependency_freeze.json").read_text(encoding="utf-8")
        )
        for item in manifest["files"]:
            assert (
                hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
                == item["sha256"]
            )
    run(a.phase, a.out)


if __name__ == "__main__":
    main()
