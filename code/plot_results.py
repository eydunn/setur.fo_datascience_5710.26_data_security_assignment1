"""Turn the runner's CSV into figures and tables for the report.

    python plot_results.py
    python plot_results.py --tradeoff-n 40 --speedup-n 48 --extrapolate 64 80 128

Everything goes to results/report/, each figure as PNG and PDF:

    hashes_vs_n        median hashes per configuration, and 2^(n/2)
    hashes_normalized  hashes / 2^(n/2): each method's constant factor
    time_vs_n          median time, failed runs as crosses, fitted trend
    memory_vs_n        median peak memory the search allocated (tracemalloc),
                       and the interpreter's resident memory for scale
    tradeoff           time against memory at one n
    speedup            parallel speedup against the number of workers
    summary.csv        one line per configuration and n, with an example pair
    extrapolation.csv  the fitted time trend evaluated at larger n

Lines are medians over the seeds; shaded bands run from minimum to maximum.
The plots against n show only configurations run at two or more values of n.
"""

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files, no window needed
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator

HERE = Path(__file__).resolve().parent
NUMERIC = {"n": int, "seed": int, "distinguish_bits": int, "workers": int,
           "hashes": int, "seconds": float, "peak_bytes": int,
           "baseline_bytes": int, "children_peak_bytes": int}


# ---------------------------------------------------------------- helpers

def load(path):
    rows = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            for key, kind in NUMERIC.items():
                value = row.get(key)
                row[key] = kind(value) if value not in (None, "") else None
            rows.append(row)
    return rows


def group(rows, ok):
    """config -> n -> rows, for successful (ok=True) or failed runs."""
    out = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if (row["status"] == "ok") == ok:
            out[row["config"]][row["n"]].append(row)
    return out


def series(by_n, key, scale=lambda n: 1):
    """Sorted n, and median, minimum, maximum of key / scale(n)."""
    ns, med, lo, hi = [], [], [], []
    for n in sorted(by_n):
        values = [r[key] / scale(n) for r in by_n[n] if r[key] is not None]
        if values:
            ns.append(n)
            med.append(statistics.median(values))
            lo.append(min(values))
            hi.append(max(values))
    return np.array(ns), np.array(med), np.array(lo), np.array(hi)


def human_bytes(b, _pos=None):
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    while b >= 1024 and i < len(units) - 1:
        b /= 1024
        i += 1
    return f"{b:.3g} {units[i]}"


def human_time(s):
    year = 365.25 * 86400
    if s >= 1e6 * year:
        return f"{s / year:.1e} years"
    if s >= 1000 * year:
        return f"{s / year:,.0f} years"
    for size, unit in [(year, "years"), (86400, "days"),
                       (3600, "h"), (60, "min"), (1, "s")]:
        if s >= size:
            return f"{s / size:.3g} {unit}"
    return f"{s * 1000:.3g} ms"


def new_axes(title, xlabel, ylabel):
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, which="major", alpha=0.3)
    return fig, ax


def save(fig, outdir, name):
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(outdir / f"{name}.{ext}", dpi=150)
    plt.close(fig)
    print(f"wrote {name}.png and {name}.pdf")


def plot_band(ax, ns, med, lo, hi, color, label):
    ax.plot(ns, med, marker="o", color=color, label=label)
    if len(ns) > 1:
        ax.fill_between(ns, lo, hi, color=color, alpha=0.15, linewidth=0)
    else:
        ax.vlines(ns, lo, hi, color=color, alpha=0.4)


def n_ticks(ax, groups):
    """Ticks at the n values that were run (multiples of 8), unless there
    are too many to label."""
    ns = sorted({n for g in groups for by_n in g.values() for n in by_n})
    if len(ns) <= 12:
        ax.set_xticks(ns)
    else:
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))


def birthday(n):
    return 2.0 ** (n / 2)


# ---------------------------------------------------------------- figures

def fig_hashes(ok, colors, outdir):
    fig, ax = new_axes("Hashes until a collision", "n (prefix bits)",
                       "SHA-256 evaluations")
    ax.set_yscale("log", base=2)
    for config, by_n in ok.items():
        plot_band(ax, *series(by_n, "hashes"), colors[config], config)
    all_n = sorted({n for by_n in ok.values() for n in by_n})
    ax.plot(all_n, [birthday(n) for n in all_n], "k--", label=r"$2^{n/2}$")
    n_ticks(ax, [ok])
    ax.legend(fontsize=8)
    save(fig, outdir, "hashes_vs_n")


def fig_normalized(ok, colors, outdir):
    fig, ax = new_axes("Work relative to the birthday bound", "n (prefix bits)",
                       r"hashes / $2^{n/2}$")
    for config, by_n in ok.items():
        plot_band(ax, *series(by_n, "hashes", scale=birthday), colors[config], config)
    ax.axhline(1, color="k", linestyle="--", linewidth=1)
    ax.set_ylim(bottom=0)
    n_ticks(ax, [ok])
    ax.legend(fontsize=8)
    save(fig, outdir, "hashes_normalized")


def fit_time(by_n, min_seconds=0.05):
    """Straight line through log2(median seconds) against n. Very short runs
    are left out: interpreter start-up and noise dominate them."""
    ns, med, _, _ = series(by_n, "seconds")
    keep = med >= min_seconds
    if len(set(ns[keep])) < 3:
        return None
    slope, intercept = np.polyfit(ns[keep], np.log2(med[keep]), 1)
    return slope, intercept


def fig_time(ok, failed, colors, outdir, ahead=8):
    fig, ax = new_axes("Time until a collision", "n (prefix bits)", "seconds")
    ax.set_yscale("log")
    fits = {}
    for config, by_n in ok.items():
        ns, med, lo, hi = series(by_n, "seconds")
        plot_band(ax, ns, med, lo, hi, colors[config], config)
        fit = fit_time(by_n)
        if fit:
            fits[config] = fit
            xs = np.linspace(ns.min(), ns.max() + ahead, 50)
            ax.plot(xs, 2 ** (fit[0] * xs + fit[1]), ":", color=colors[config])
    any_failed = False
    for config, by_n in failed.items():
        for n, rows in by_n.items():
            for r in rows:
                if r["seconds"] is not None:
                    ax.scatter([n], [r["seconds"]], marker="x", s=70,
                               color=colors[config], zorder=5)
                    any_failed = True
    lo, hi = ax.get_ylim()
    for label, s in [("1 min", 60), ("1 h", 3600), ("1 day", 86400)]:
        if lo < s < hi:
            ax.axhline(s, color="gray", linewidth=0.8, linestyle="-.")
            ax.text(0.01, s, label, transform=ax.get_yaxis_transform(),
                    va="top", fontsize=8, color="gray")
    handles, labels = ax.get_legend_handles_labels()
    if fits:
        handles.append(Line2D([], [], color="gray", linestyle=":"))
        labels.append("fitted trend")
    if any_failed:
        handles.append(Line2D([], [], color="gray", marker="x", linestyle=""))
        labels.append("failed run")
    ax.legend(handles, labels, fontsize=8)
    n_ticks(ax, [ok, failed])
    save(fig, outdir, "time_vs_n")
    return fits


def fig_memory(ok, colors, outdir):
    fig, ax = new_axes("Peak memory allocated by the search", "n (prefix bits)",
                       "peak traced memory (tracemalloc)")
    ax.set_yscale("log", base=2)
    baselines = [r["baseline_bytes"] for by_n in ok.values()
                 for rows in by_n.values() for r in rows if r["baseline_bytes"]]
    for config, by_n in ok.items():
        plot_band(ax, *series(by_n, "peak_bytes"), colors[config], config)
    if baselines:
        ax.axhline(statistics.median(baselines), color="gray", linestyle="--",
                   linewidth=1, label="interpreter resident memory (not traced)")
    ax.yaxis.set_major_formatter(FuncFormatter(human_bytes))
    n_ticks(ax, [ok])
    ax.legend(fontsize=8)
    save(fig, outdir, "memory_vs_n")


def fig_tradeoff(rows, ok, colors, outdir, n=None):
    single = {c: by_n for c, by_n in ok.items() if not c.startswith("parallel")}
    if n is None:
        counts = defaultdict(int)
        for by_n in single.values():
            for k in by_n:
                counts[k] += 1
        shared = [k for k, c in counts.items() if c >= 2]
        if not shared:
            print("tradeoff: no n where two methods both finished; skipped")
            return
        n = max(shared)
    points = []
    for config, by_n in single.items():
        if n not in by_n:
            continue
        mems = [r["peak_bytes"] for r in by_n[n] if r["peak_bytes"]]
        if not mems:
            print(f"tradeoff: {config} has no peak_bytes at n = {n}; left out")
            continue
        points.append((config, statistics.median(r["seconds"] for r in by_n[n]),
                       statistics.median(mems), by_n[n][0]["distinguish_bits"]))
    if not points:
        print(f"tradeoff: no finished single-process runs at n = {n}; skipped")
        return
    fig, ax = new_axes(f"Time against memory at n = {n}", "median seconds",
                       "median peak memory")
    ax.set_xscale("log")
    ax.set_yscale("log", base=2)
    chain = []  # distinguished points, joined in order of d
    for config, sec, mem, d in points:
        ax.scatter([sec], [mem], s=60, color=colors[config], zorder=3)
        ax.annotate(config, (sec, mem), textcoords="offset points",
                    xytext=(6, 4), fontsize=8)
        if config.startswith("distinguished"):
            chain.append((d, sec, mem))
    if len(chain) > 1:
        chain.sort()
        ax.plot([c[1] for c in chain], [c[2] for c in chain], color="gray",
                linewidth=0.8, zorder=2)
    ax.yaxis.set_major_formatter(FuncFormatter(human_bytes))
    ax.margins(0.2)
    save(fig, outdir, "tradeoff")


def fig_speedup(rows, outdir, n=None):
    par = [r for r in rows if r["status"] == "ok" and r["method"] == "parallel"]
    if n is None:
        worker_counts = defaultdict(set)
        for r in par:
            worker_counts[r["n"]].add(r["workers"])
        candidates = [k for k, w in worker_counts.items() if len(w) >= 2]
        if not candidates:
            print("speedup: no n with parallel runs at two worker counts; skipped")
            return
        n = max(candidates)
    times = defaultdict(lambda: defaultdict(list))  # d -> workers -> seconds
    for r in par:
        if r["n"] == n:
            times[r["distinguish_bits"]][r["workers"]].append(r["seconds"])
    lines = []  # (d, baseline source, worker counts, speedups)
    for d, by_w in sorted(times.items()):
        if 1 in by_w:
            base, source = statistics.median(by_w[1]), "1 worker"
        else:
            single = [r["seconds"] for r in rows
                      if r["status"] == "ok" and r["method"] == "distinguished"
                      and r["n"] == n and r["distinguish_bits"] == d]
            if not single:
                print(f"speedup: no 1-worker or distinguished baseline for d = {d}")
                continue
            base, source = statistics.median(single), "distinguished"
        ws = sorted(by_w)
        lines.append((d, source, ws, [base / statistics.median(by_w[w]) for w in ws]))
    if not lines:
        print(f"speedup: no parallel runs with a baseline at n = {n}; skipped")
        return
    fig, ax = new_axes(f"Parallel speedup at n = {n}", "worker processes", "speedup")
    top = 1
    for d, source, ws, speedups in lines:
        ax.plot(ws, speedups, marker="o", label=f"d = {d} (baseline: {source})")
        top = max(top, max(ws))
    ax.plot([1, top], [1, top], "k--", linewidth=1, label="perfect scaling")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(fontsize=8)
    save(fig, outdir, "speedup")


# ---------------------------------------------------------------- tables

def write_summary(ok, failed, outdir):
    path = outdir / "summary.csv"
    keys = sorted({(c, n) for g in (ok, failed) for c, by_n in g.items() for n in by_n})
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["config", "n", "runs_ok", "runs_failed", "median_hashes",
                    "hashes_over_2^(n/2)", "median_seconds", "median_peak_bytes",
                    "example_message", "example_other", "prefix"])
        for config, n in keys:
            good = sorted(ok[config][n], key=lambda r: r["seed"])
            bad = failed[config][n]
            if good:
                med_h = statistics.median(r["hashes"] for r in good)
                mems = [r["peak_bytes"] for r in good if r["peak_bytes"]]
                ex = good[0]
                w.writerow([config, n, len(good), len(bad), int(med_h),
                            f"{med_h / birthday(n):.2f}",
                            f"{statistics.median(r['seconds'] for r in good):.4f}",
                            int(statistics.median(mems)) if mems else "",
                            ex["message"], ex["other"], ex["prefix"]])
            else:
                w.writerow([config, n, 0, len(bad)] + [""] * 7)
    print(f"wrote {path.name}")


def write_extrapolation(fits, targets, outdir):
    if not fits:
        print("extrapolation: needs three n values per method above 0.05 s; skipped")
        return
    path = outdir / "extrapolation.csv"
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["config", "slope"] + [f"seconds_n{t}" for t in targets]
                   + [f"readable_n{t}" for t in targets])
        print(f"\n{'fitted time':<24} {'slope':>6}"
              + "".join(f"{'n=' + str(t):>20}" for t in targets))
        for config, (slope, intercept) in sorted(fits.items()):
            secs = [2 ** (slope * t + intercept) for t in targets]
            w.writerow([config, f"{slope:.3f}"] + [f"{s:.4g}" for s in secs]
                       + [human_time(s) for s in secs])
            print(f"{config:<24} {slope:>6.3f}"
                  + "".join(f"{human_time(s):>20}" for s in secs))
    print(f"(a slope near 0.5 means time grows like 2^(n/2))\nwrote {path.name}")


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Plot the collision-search results.")
    parser.add_argument("--results", type=Path,
                        default=HERE / "results" / "results.csv")
    parser.add_argument("--out", type=Path, default=HERE / "results" / "report")
    parser.add_argument("--tradeoff-n", type=int,
                        help="n for the time-memory plot (default: largest shared n)")
    parser.add_argument("--speedup-n", type=int,
                        help="n for the speedup plot (default: largest possible)")
    parser.add_argument("--extrapolate", nargs="+", type=int, default=[64, 80, 128],
                        help="n values for the fitted time table (default 64 80 128)")
    args = parser.parse_args()

    rows = load(args.results)
    if not rows:
        raise SystemExit(f"{args.results} has no runs yet")
    args.out.mkdir(parents=True, exist_ok=True)

    ok, failed = group(rows, ok=True), group(rows, ok=False)
    configs = sorted({r["config"] for r in rows})
    palette = plt.get_cmap("tab10").colors
    colors = {c: palette[i % len(palette)] for i, c in enumerate(configs)}

    # Lines against n are drawn only for configurations run at several n;
    # one-n sweeps (values of d, worker counts) belong to tradeoff and speedup.
    # A configuration that failed at its second n still counts as run at two.
    ran_at = defaultdict(set)
    for r in rows:
        ran_at[r["config"]].add(r["n"])
    over_n = {c: by_n for c, by_n in ok.items() if len(ran_at[c]) >= 2} or ok
    failed_over_n = {c: by_n for c, by_n in failed.items()
                     if c in over_n or c not in ok}

    if ok:
        fig_hashes(over_n, colors, args.out)
        fig_normalized(over_n, colors, args.out)
        fits = fig_time(over_n, failed_over_n, colors, args.out)
        fig_memory(over_n, colors, args.out)
        fig_tradeoff(rows, ok, colors, args.out, args.tradeoff_n)
        fig_speedup(rows, args.out, args.speedup_n)
        write_extrapolation(fits, args.extrapolate, args.out)
    write_summary(ok, failed, args.out)


if __name__ == "__main__":
    main()
