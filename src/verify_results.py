"""Rebuild every export independently with integer cross-products and exact enclosures."""

import argparse, csv, hashlib, json, sqlite3
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    checks = 0

    def check(condition):
        nonlocal checks
        assert condition, f"Independent result condition {checks+1} failed"
        checks += 1

    def read(name):
        return list(
            csv.DictReader((a.results / (name + ".csv")).open(encoding="utf-8"))
        )

    counts = list(csv.DictReader((ROOT / "data/counts.csv").open(encoding="utf-8")))
    db = sqlite3.connect(":memory:")
    db.execute("create table counts(v text,r text,t text,x integer,primary key(v,r,t))")
    for row in counts:
        check(
            row["unit"] == "ten_thousand_persons"
            and row["sex"] == "total"
            and row["concept"] == "employed_persons"
            and row["adjustment"] == "original"
            and row["native_type"] == "n"
            and row["formula"] == "false"
        )
        val = Q(row["value_token"])
        check(val.denominator == 1 and val > Q(1, 2))
        db.execute(
            "insert into counts values(?,?,?,?)",
            (row["vintage"], row["region"], row["period"], int(val)),
        )
    check(db.execute("select count(*) from counts").fetchone()[0] == 288)
    expected = {
        (v, g, f"{y}-{m:02}")
        for v in ["pre2022", "current"]
        for g in ["Southern-Kanto", "Kinki"]
        for y in range(2016, 2022)
        for m in range(1, 13)
    }
    check(set(db.execute("select v,r,t from counts")) == expected)

    def count(v, g, t):
        return db.execute(
            "select x from counts where v=? and r=? and t=?", (v, g, t)
        ).fetchone()[0]

    ex = json.loads((a.results / "execution.json").read_text(encoding="utf-8"))
    phase = ex["phase"]
    years = range(2017, 2019) if phase == "development" else range(2019, 2022)
    periodkeys = {
        (g, f"{y}-{m:02}")
        for g in ["Southern-Kanto", "Kinki"]
        for y in years
        for m in range(1, 13)
    }
    growth = read("growth")
    lookup = {}
    signs = {}
    states = {}
    check(len(growth) == 3 * len(periodkeys))
    check({(r["region"], r["period"]) for r in growth} == periodkeys)
    for row in growth:
        g, t, method = row["region"], row["period"], row["method"]
        key = (g, t, method)
        check(key not in lookup)
        lag = str(int(t[:4]) - 1) + t[4:]
        check(row["lag_period"] == lag)
        av = "pre2022" if method == "archive" else "current"
        bv = "current" if method == "current" else "pre2022"
        check(method in ["archive", "current", "mixed"])
        n, d = count(av, g, t), count(bv, g, lag)
        x = Q(n - d, d)
        lo = Q(2 * n - 1, 2 * d + 1) - 1
        hi = Q(2 * n + 1, 2 * d - 1) - 1
        s = 1 if n > d else (-1 if n < d else 0)
        cert = (
            "positive"
            if 2 * n - 1 > 2 * d + 1
            else ("negative" if 2 * n + 1 < 2 * d - 1 else "ambiguous")
        )
        for field, value in [
            ("numerator", n),
            ("denominator", d),
            ("growth", x),
            ("lower", lo),
            ("upper", hi),
            ("point_sign", s),
        ]:
            check(Q(row[field]) == value)
        check(row["certified_sign"] == cert)
        check(lo <= x <= hi)
        lookup[key] = (x, lo, hi)
        signs[key] = cert
    alerts = read("alerts")
    check(len(alerts) == 6 * len(periodkeys))
    for r in alerts:
        key = (r["region"], r["period"], r["method"])
        x, lo, hi = lookup[key]
        q = Q(r["threshold"])
        check(q in [Q(1, 200), Q(1, 100)])
        cert = (
            "alert"
            if min(abs(lo), abs(hi)) >= q and lo * hi > 0
            else ("no_alert" if lo > -q and hi < q else "ambiguous")
        )
        check(r["certified_alert"] == cert)
        check(int(r["point_alert"]) == int(abs(x) >= q))
        ak = (*key, q)
        check(ak not in states)
        states[ak] = (int(abs(x) >= q), cert)
    pairs = read("pairs")
    check(len(pairs) == 2 * len(periodkeys))
    pairkeys = set()
    for r in pairs:
        g, t = r["region"], r["period"]
        method = r["comparison"].replace("_vs_current", "")
        check(method in ["archive", "mixed"])
        check((g, t, method) not in pairkeys)
        pairkeys.add((g, t, method))
        x = lookup[g, t, method][0]
        ref = lookup[g, t, "current"][0]
        xs = signs[g, t, method]
        rs = signs[g, t, "current"]
        values = dict(
            difference_pp=100 * (x - ref),
            absolute_difference_pp=100 * abs(x - ref),
            sign_disagree=int((x > 0) - (x < 0) != (ref > 0) - (ref < 0)),
            strict_opposite=int(x * ref < 0),
            rounding_robust_opposite=int(
                xs in ["positive", "negative"]
                and rs in ["positive", "negative"]
                and xs != rs
            ),
        )
        for q, suffix in [(Q(1, 200), "005"), (Q(1, 100), "010")]:
            point, cert = states[g, t, method, q]
            rp, rc = states[g, t, "current", q]
            both = cert != "ambiguous" and rc != "ambiguous"
            values.update(
                {
                    "point_alert_mismatch_" + suffix: int(point != rp),
                    "both_certified_" + suffix: int(both),
                    "certified_alert_mismatch_" + suffix: int(both and cert != rc),
                }
            )
        for k, v in values.items():
            check(Q(r[k]) == v)
    summaries = read("summary")
    check(len(summaries) == 6)
    for r in summaries:
        group = [
            p
            for p in pairs
            if p["comparison"] == r["comparison"]
            and (r["region"] == "All" or p["region"] == r["region"])
        ]
        check(len(group) == int(r["pairs"]))
        diffs = [
            abs(
                lookup[
                    p["region"], p["period"], p["comparison"].replace("_vs_current", "")
                ][0]
                - lookup[p["region"], p["period"], "current"][0]
            )
            * 100
            for p in group
        ]
        check(Q(r["mean_absolute_difference_pp"]) == sum(diffs) / len(diffs))
        check(Q(r["max_absolute_difference_pp"]) == max(diffs))
        for k in group[0]:
            if k not in [
                "phase",
                "region",
                "period",
                "comparison",
                "difference_pp",
                "absolute_difference_pp",
            ]:
                check(int(r[k]) == sum(int(p[k]) for p in group))
    levels = read("levels")
    check(len(levels) == 72)
    for r in levels:
        o = count("pre2022", r["region"], r["period"])
        n = count("current", r["region"], r["period"])
        for k, v in [
            ("old_count", o),
            ("current_count", n),
            ("revision_ten_thousand", n - o),
            ("relative_revision", Q(n - o, o)),
        ]:
            check(Q(r[k]) == v)
    check(ex["pairs"] == len(periodkeys))
    check(
        ex["input_sha256"]
        == hashlib.sha256((ROOT / "data/counts.csv").read_bytes()).hexdigest()
    )
    result = dict(
        status="PASS_INDEPENDENT_EXACT_RECONSTRUCTION",
        phase=phase,
        checks=checks,
        pairs=len(periodkeys),
        files=6,
        source_network=False,
    )
    target = a.out or a.results / "verification.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
