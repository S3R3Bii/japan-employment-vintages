"""Offline reference guard for one explicitly versioned year-on-year count pair."""

import argparse, json
from fractions import Fraction
from pathlib import Path
from analyze import growth, certified_sign, previous_year

IDENTITY = ("region", "concept", "sex", "adjustment", "unit", "dataset_vintage")


def compare(current, lag):
    try:
        if any(not isinstance(r, dict) for r in [current, lag]):
            return dict(status="unavailable", reason="Record must be an object")
        if any(
            not isinstance(r.get(k), str) or not r[k].strip()
            for r in [current, lag]
            for k in IDENTITY
        ):
            return dict(
                status="unavailable", reason="Missing count identity or dataset version"
            )
        if any(current[k] != lag[k] for k in IDENTITY):
            return dict(
                status="unavailable", reason="Different identity or dataset version"
            )
        if (
            current["concept"] != "employed_persons"
            or current["sex"] != "total"
            or current["adjustment"] != "original"
            or current["unit"] != "ten_thousand_persons"
        ):
            return dict(status="unavailable", reason="Unsupported count definition")
        if (
            len(current["period"]) != 7
            or len(lag["period"]) != 7
            or previous_year(current["period"]) != lag["period"]
        ):
            return dict(
                status="unavailable",
                reason="Comparison must use the same month one year earlier",
            )
        if any(not isinstance(r["count"], str) for r in [current, lag]):
            return dict(
                status="unavailable",
                reason="Use native count strings, not binary floats",
            )
        values = [Fraction(r["count"]) for r in [current, lag]]
        if any(v.denominator != 1 or v <= 0 for v in values):
            return dict(
                status="unavailable", reason="Positive rounded integer counts required"
            )
        point, lo, hi = growth(*values)
        return dict(
            status="available",
            growth=str(point),
            rounding_lower=str(lo),
            rounding_upper=str(hi),
            certified_sign=certified_sign(lo, hi),
            unit="fractional_year_on_year_growth",
            dataset_vintage=current["dataset_vintage"],
            sampling_uncertainty="not estimated",
        )
    except (KeyError, ValueError, TypeError, ZeroDivisionError, AssertionError):
        return dict(status="unavailable", reason="Invalid count, period or identity")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("current", type=Path)
    p.add_argument("lag", type=Path)
    a = p.parse_args()
    print(
        json.dumps(
            compare(
                json.loads(a.current.read_text(encoding="utf-8")),
                json.loads(a.lag.read_text(encoding="utf-8")),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
