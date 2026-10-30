"""Three original figures with explicit source queries and inspectable SVG marks."""

import csv, hashlib, json, shutil
from fractions import Fraction as F
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "svg.fonttype": "none",
        "path.simplify": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": "#233b49",
        "text.color": "#233b49",
        "axes.edgecolor": "#a5b2b7",
        "savefig.facecolor": "white",
    }
)
BLUE = "#235d72"
ORANGE = "#b65f27"
GREY = "#a5b2b7"


def read(path):
    return list(csv.DictReader((ROOT / path).open(encoding="utf-8")))


def save(fig, axes, name, items):
    for i, ax in enumerate(axes):
        ax.patch.set_gid(f"data-area-{i}")
    for item in items:
        item.pop("artist").set_gid(item["id"])
    files = []
    for ext in ["pdf", "svg", "png"]:
        path = ROOT / "figures" / f"{name}.{ext}"
        fig.savefig(
            path,
            dpi=155 if ext == "png" else 100,
            metadata={"Date": None} if ext == "svg" else None,
        )
        if ext == "svg":
            path.write_bytes(
                (
                    "\n".join(
                        line.rstrip()
                        for line in path.read_text(encoding="utf-8").splitlines()
                    )
                    + "\n"
                ).encode()
            )
        files.append(path)
    shutil.copyfile(
        ROOT / "figures" / f"{name}.pdf", ROOT / "paper/images" / f"{name}.pdf"
    )
    entry = dict(
        figure=name,
        axes=[dict(xlim=list(a.get_xlim()), ylim=list(a.get_ylim())) for a in axes],
        items=items,
        files={
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
    )
    plt.close(fig)
    return entry


def main():
    maps = []
    levels = read("results/development/levels.csv") + read("results/later/levels.csv")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    fig.subplots_adjust(left=0.10, right=0.97, bottom=0.18, top=0.82)
    items = []
    for region, color in [("Southern-Kanto", BLUE), ("Kinki", ORANGE)]:
        rows = sorted(
            [r for r in levels if r["region"] == region], key=lambda r: r["period"]
        )
        y = [float(F(r["revision_ten_thousand"])) for r in rows]
        (line,) = ax.plot(range(72), y, color=color, lw=1.8, label=region)
        items.append(
            dict(
                artist=line,
                id="revision-" + region,
                kind="revision_line",
                region=region,
                values_exact=[r["revision_ten_thousand"] for r in rows],
                axis=0,
            )
        )
    ax.set(
        xlim=(-1, 72),
        ylim=(0, 16),
        ylabel="Current minus archive (10,000 persons)",
        xlabel="Source month (both versions)",
    )
    ax.set_xticks(
        [0, 12, 24, 36, 48, 60, 71],
        ["2016", "2017", "2018", "2019", "2020", "2021", "Dec 2021"],
    )
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    fig.suptitle(
        "Both regional count series were revised upward",
        x=0.10,
        ha="left",
        fontweight="bold",
    )
    maps.append(save(fig, [ax], "count_revisions", items))
    growth = read("results/later/growth.csv")
    lookup = {(r["region"], r["period"], r["method"]): r for r in growth}
    fig, ax = plt.subplots(figsize=(7, 5.3))
    fig.subplots_adjust(left=0.13, right=0.96, bottom=0.15, top=0.84)
    items = []
    for region, color in [("Southern-Kanto", BLUE), ("Kinki", ORANGE)]:
        periods = sorted({r["period"] for r in growth if r["region"] == region})
        x = [100 * float(F(lookup[region, t, "current"]["growth"])) for t in periods]
        y = [100 * float(F(lookup[region, t, "mixed"]["growth"])) for t in periods]
        (marks,) = ax.plot(
            x,
            y,
            linestyle="none",
            marker="o",
            ms=4.6,
            alpha=0.8,
            color=color,
            label=region,
        )
        items.append(
            dict(
                artist=marks,
                id="growth-" + region,
                kind="growth_markers",
                region=region,
                periods=periods,
                values_exact=[
                    [
                        lookup[region, t, "current"]["growth"],
                        lookup[region, t, "mixed"]["growth"],
                    ]
                    for t in periods
                ],
                axis=0,
            )
        )
    ax.plot([-2.5, 3.7], [-2.5, 3.7], color=GREY, lw=1, zorder=0, label="Same growth")
    ax.axhline(0, color=GREY, lw=0.6)
    ax.axvline(0, color=GREY, lw=0.6)
    ax.set(
        xlim=(-2.5, 3.7),
        ylim=(-2.5, 3.7),
        xlabel="Current coherent year-on-year growth (%)",
        ylabel="Authored mixed-vintage growth (%)",
    )
    ax.legend(frameon=False, loc="upper left")
    ax.grid(alpha=0.12)
    fig.suptitle(
        "Mixing versions raises the apparent growth signal",
        x=0.13,
        ha="left",
        fontweight="bold",
    )
    fig.text(0.13, 0.89, "72 later region-month pairs, 2019–2021", fontsize=10)
    maps.append(save(fig, [ax], "growth_splice", items))
    summary = next(
        r
        for r in read("results/later/summary.csv")
        if r["region"] == "All" and r["comparison"] == "mixed_vs_current"
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.25, top=0.76, wspace=0.34)
    items = []
    for index, suffix in enumerate(["005", "010"]):
        for kind, offset, color, field in [
            ("point", -0.18, BLUE, "point_alert_mismatch_"),
            ("certified", 0.18, ORANGE, "certified_alert_mismatch_"),
        ]:
            value = int(summary[field + suffix])
            bar = axes[0].bar(
                index + offset,
                value,
                width=0.30,
                color=color,
                label=kind.capitalize() if index == 0 else None,
            )[0]
            denominator = (
                int(summary["pairs"])
                if kind == "point"
                else int(summary["both_certified_" + suffix])
            )
            axes[0].text(
                index + offset,
                value + 0.3,
                f"{value}/{denominator}",
                ha="center",
                fontsize=9,
            )
            items.append(
                dict(
                    artist=bar,
                    id=f"error-{suffix}-{kind}",
                    kind="error_bar",
                    suffix=suffix,
                    field=field + suffix,
                    x=index + offset,
                    width=0.30,
                    bottom=0,
                    value_exact=str(value),
                    axis=0,
                )
            )
        both = int(summary["both_certified_" + suffix])
        ambiguous = int(summary["pairs"]) - both
        for kind, bottom, value, color in [
            ("both", 0, both, BLUE),
            ("ambiguous", both, ambiguous, GREY),
        ]:
            bar = axes[1].bar(
                index,
                value,
                bottom=bottom,
                width=0.58,
                color=color,
                label=(
                    "Both certified"
                    if kind == "both" and index == 0
                    else ("At least one ambiguous" if index == 0 else None)
                ),
            )[0]
            items.append(
                dict(
                    artist=bar,
                    id=f"coverage-{suffix}-{kind}",
                    kind="coverage_bar",
                    suffix=suffix,
                    field=kind,
                    x=index,
                    width=0.58,
                    bottom=bottom,
                    value_exact=str(value),
                    axis=1,
                )
            )
        axes[1].text(index, 74, f"{both} + {ambiguous}", ha="center", fontsize=9)
    axes[0].set(
        xlim=(-0.6, 1.6),
        ylim=(0, 16),
        ylabel="Classification disagreements",
        title="Same fixed threshold; different versions",
    )
    axes[1].set(
        xlim=(-0.6, 1.6),
        ylim=(0, 80),
        ylabel="Later region-month pairs",
        title="Rounding certification coverage",
    )
    for ax in axes:
        ax.set_xticks([0, 1], ["0.5%", "1%"])
        ax.set_xlabel("Illustrative absolute-growth threshold")
        ax.grid(axis="y", alpha=0.14)
        ax.set_axisbelow(True)
    axes[0].legend(frameon=False, loc="upper right", fontsize=9)
    axes[1].legend(
        frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.27), fontsize=8
    )
    fig.suptitle(
        "Rounding leaves some comparisons undecided",
        x=0.07,
        ha="left",
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.85,
        "Point mismatches use all 72 pairs. Certified mismatches use only the stated certified denominator.",
        fontsize=9,
    )
    maps.append(save(fig, list(axes), "threshold_coverage", items))
    (ROOT / "figures/value_map.json").write_bytes(
        (json.dumps(maps, indent=2) + "\n").encode()
    )
    print("THREE_FIGURES_EXPORTED")


if __name__ == "__main__":
    main()
