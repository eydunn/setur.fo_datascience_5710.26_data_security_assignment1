"""Run many searches, one process each, and append one CSV row per run.

    python run_experiments.py --methods hash_table floyd --n 16 48 --step 8 --trials 10

Every run is a fresh `python cli.py ... --json`, so each one starts with a
clean memory peak and can be stopped at --timeout. n follows the menu's
rule: a multiple of 8, from 8 to 256, so --n takes multiples of 8 and
--step is a multiple of 8. A row is appended to the
CSV as soon as its run ends, so an interrupted campaign keeps what it
finished, and running the same command again skips the runs already there.

The loop goes n by n, running every configuration at one n before moving
up, so stopping early still leaves comparable data. A configuration (a
method with its settings) stops climbing at its first failure: a timeout,
running out of memory, a crash, or a pair that does not verify. That row is
kept, because where the machine runs out is part of the result.

Distinguished points and parallel take lists of settings, one
configuration per value:

    python run_experiments.py --methods distinguished --n 40 40 \\
        --distinguish-bits 4 6 8 10 12 --trials 10
    python run_experiments.py --methods parallel --n 48 48 \\
        --distinguish-bits 12 --workers 1 2 4 8 --trials 5

The searches are deterministic: every trial of a configuration hashes the
same messages, so the trials differ only in time and memory.

--memory-limit-gb caps each run's address space (Linux), so the hash table
fails with MemoryError instead of pushing the machine into swap.

results/machine.json records the machine: CPU, cores, RAM, Python and
OpenSSL versions, whether the CPU has SHA-256 instructions (SHA-NI on x86,
the SHA2 extension on ARM), whether hashlib can use them, and how long one
hashlib.sha256 call takes in a Python loop.
"""

import argparse
import csv
import hashlib
import json
import os
import platform
import signal
import ssl
import subprocess
import sys
import time
import timeit
from datetime import datetime, timezone
from pathlib import Path

from distinguished import default_distinguish_bits
from search import D_METHODS, METHODS, check_n

HERE = Path(__file__).resolve().parent
MAIN = HERE / "cli.py"

FIELDS = ["timestamp", "config", "method", "n", "seed", "distinguish_bits",
          "workers", "status", "hashes", "seconds", "peak_bytes",
          "baseline_bytes", "children_peak_bytes", "message", "other",
          "prefix"]


def configurations(args):
    """One dict per method and setting, with a label used to group rows."""
    for method in args.methods:
        d_values = (args.distinguish_bits
                    if method in D_METHODS and args.distinguish_bits else [None])
        w_values = args.workers if method == "parallel" and args.workers else [None]
        for d in d_values:
            for w in w_values:
                label = method
                if method in D_METHODS:
                    label += f" d={d}" if d is not None else " d=n/4"
                if w is not None:
                    label += f" w={w}"
                yield {"config": label, "method": method,
                       "distinguish_bits": d, "workers": w}


def command(cfg, n, seed):
    cmd = [sys.executable, str(MAIN), cfg["method"],
           "--n", str(n), "--seed", str(seed), "--json"]
    if cfg["distinguish_bits"] is not None:
        cmd += ["--distinguish-bits", str(cfg["distinguish_bits"])]
    if cfg["workers"] is not None:
        cmd += ["--workers", str(cfg["workers"])]
    return cmd


def memory_limit(gb):
    """A function the child runs before starting, capping its memory."""
    if gb is None or os.name != "posix":
        return None
    import resource
    limit = int(gb * 2 ** 30)

    def apply():
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (ValueError, OSError):
            pass  # not enforced on this system (e.g. macOS)
    return apply


def kill_tree(proc):
    """Stop the run and any worker processes it started."""
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        pass


def last_json_line(text):
    for line in reversed(text.strip().splitlines()):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return None
    return None


def run_one(cfg, n, seed, args):
    options = {}
    if os.name == "posix":
        # Own process group, so a timeout can stop parallel's workers too.
        options["start_new_session"] = True
        options["preexec_fn"] = memory_limit(args.memory_limit_gb)
    started = time.perf_counter()
    proc = subprocess.Popen(command(cfg, n, seed), cwd=HERE, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            **options)
    try:
        out, err = proc.communicate(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        proc.communicate()
        return {"status": "timeout", "seconds": args.timeout}
    except KeyboardInterrupt:
        kill_tree(proc)
        raise
    elapsed = time.perf_counter() - started

    result = last_json_line(out)
    if result is not None:  # ok, invalid, or out_of_memory
        result.setdefault("seconds", elapsed)
        return result
    if "MemoryError" in err:
        return {"status": "out_of_memory", "seconds": elapsed}
    if proc.returncode < 0:
        return {"status": f"killed by signal {-proc.returncode}",
                "seconds": elapsed}
    for line in err.strip().splitlines()[-6:]:
        print("    | " + line, file=sys.stderr)
    return {"status": "error", "seconds": elapsed}


def human_bytes(b):
    if b in (None, ""):
        return "-"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    b, i = float(b), 0
    while b >= 1024 and i < len(units) - 1:
        b /= 1024
        i += 1
    return f"{b:.1f} {units[i]}"


def report(row):
    hashes = f"{row['hashes']:,}" if row.get("hashes") is not None else "-"
    seconds = row.get("seconds")
    seconds = f"{seconds:.2f} s" if seconds is not None else "-"
    print(f"{row['config']:<24} n={row['n']:<3} seed={row['seed']:<3} "
          f"{row['status']:<14} {hashes:>16} hashes {seconds:>10} "
          f"{human_bytes(row.get('peak_bytes')):>10}", flush=True)


def append(path, row):
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow(row)


def previous_runs(path):
    """Runs already in the CSV, and the n where each configuration failed."""
    done, stopped = set(), {}
    if path.exists():
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                n = int(row["n"])
                done.add((row["config"], n, int(row["seed"])))
                if row["status"] != "ok":
                    stopped[row["config"]] = min(n, stopped.get(row["config"], n))
    return done, stopped


def cpu_name():
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def sha_instructions():
    """Does the CPU have SHA-256 instructions? Returns (True, False or None
    for unknown, and where the answer came from)."""
    if sys.platform.startswith("linux"):
        try:
            lines = Path("/proc/cpuinfo").read_text().splitlines()
        except OSError:
            return None, "/proc/cpuinfo unreadable"
        for line in lines:
            key, _, value = line.partition(":")
            if key.strip() in ("flags", "Features"):  # x86, ARM
                words = value.split()
                return "sha_ni" in words or "sha2" in words, f"/proc/cpuinfo {key.strip()}"
        return None, "/proc/cpuinfo lists no flags"

    if sys.platform == "darwin":
        checks = [("hw.optional.arm.FEAT_SHA256", lambda out: out.strip() == "1"),
                  ("machdep.cpu.leaf7_features", lambda out: "SHA" in out.upper().split())]
        for name, test in checks:
            try:
                out = subprocess.run(["sysctl", "-n", name], capture_output=True,
                                     text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if out.returncode == 0 and out.stdout.strip():
                return test(out.stdout), f"sysctl {name}"
        return None, "sysctl gave no answer"

    try:
        import cpuinfo  # pip install py-cpuinfo
    except ImportError:
        return None, "unknown on this system; pip install py-cpuinfo to detect it"
    flags = set(cpuinfo.get_cpu_info().get("flags", []))
    return bool(flags & {"sha", "sha_ni", "sha2"}), "py-cpuinfo"


def python_ns_per_sha256():
    """Fastest of three timings of hashlib.sha256 on a short message."""
    times = timeit.repeat("sha256(m).digest()", number=200_000, repeat=3,
                          setup="from hashlib import sha256; m = b'12345678'")
    return round(min(times) / 200_000 * 1e9)


def machine_info():
    info = {
        "recorded": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "cpu": cpu_name(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
    }
    try:
        info["ram_bytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        pass

    has_sha, source = sha_instructions()
    uses_openssl = hashlib.sha256.__name__.startswith("openssl")
    masks = {k: os.environ[k] for k in ("OPENSSL_ia32cap", "OPENSSL_armcap")
             if os.environ.get(k)}
    if not uses_openssl or has_sha is False:
        used = False      # Python's built-in SHA-256 does not use them
    elif masks or has_sha is None:
        used = None       # a mask may switch them off, or the CPU is unknown
    else:
        used = True
    info.update({
        "sha_instructions": has_sha,
        "sha_instructions_source": source,
        "hashlib_sha256": hashlib.sha256.__name__,  # openssl_sha256 = OpenSSL
        "openssl": ssl.OPENSSL_VERSION,
        "sha_instructions_used_by_hashlib": used,
        **masks,
        "python_ns_per_sha256": python_ns_per_sha256(),
    })
    return info


def main():
    parser = argparse.ArgumentParser(
        description="Run many collision searches and record one CSV row each.")
    parser.add_argument("--methods", nargs="+", choices=METHODS, required=True)
    parser.add_argument("--n", nargs=2, type=int, default=[32, 40],
                        metavar=("FIRST", "LAST"),
                        help="range of n, both ends included, multiples of 8 "
                             "from 8 to 256 (default 32 40)")
    parser.add_argument("--step", type=int, default=8,
                        help="step in n, a multiple of 8 (default 8)")
    parser.add_argument("--trials", type=int, default=5,
                        help="runs per configuration and n, seeds 0, 1, ...; "
                             "the searches are deterministic, so trials differ "
                             "only in time and memory (default 5)")
    parser.add_argument("--seed-base", type=int, default=0,
                        help="first seed (default 0)")
    parser.add_argument("--timeout", type=float, default=600,
                        help="seconds before a run counts as a timeout (default 600)")
    parser.add_argument("--memory-limit-gb", type=float,
                        help="memory cap per run, in GiB (Linux)")
    parser.add_argument("--distinguish-bits", nargs="+", type=int,
                        help="values of d to try (default n // 4)")
    parser.add_argument("--workers", nargs="+", type=int,
                        help="worker counts to try for parallel")
    parser.add_argument("--out", type=Path, default=HERE / "results" / "results.csv")
    args = parser.parse_args()
    first, last = args.n
    if check_n(first) or check_n(last) or first > last:
        parser.error("--n takes two multiples of 8 from 8 to 256, FIRST <= LAST")
    if args.step < 8 or args.step % 8:
        parser.error("--step must be a positive multiple of 8")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    info = machine_info()
    (args.out.parent / "machine.json").write_text(json.dumps(info, indent=2) + "\n")
    answer = {True: "yes", False: "no", None: "unknown"}
    cores = info["cpu_count"]
    print(f"{info['cpu']}, {cores} core{'' if cores == 1 else 's'}; "
          f"SHA instructions: {answer[info['sha_instructions']]}, "
          f"used by hashlib: {answer[info['sha_instructions_used_by_hashlib']]}; "
          f"Python: {info['python_ns_per_sha256']} ns per SHA-256 call\n")

    configs = list(configurations(args))
    done, stopped = previous_runs(args.out)
    for config, n in stopped.items():
        print(f"{config} already failed at n = {n} in {args.out.name}; skipping it")

    try:
        for n in range(args.n[0], args.n[1] + 1, args.step):
            for cfg in configs:
                if cfg["config"] in stopped:
                    continue
                for trial in range(args.trials):
                    seed = args.seed_base + trial
                    if (cfg["config"], n, seed) in done:
                        continue
                    row = {
                        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "config": cfg["config"], "method": cfg["method"],
                        "n": n, "seed": seed,
                        "distinguish_bits": cfg["distinguish_bits"],
                        "workers": cfg["workers"],
                    }
                    if cfg["method"] in D_METHODS and row["distinguish_bits"] is None:
                        row["distinguish_bits"] = default_distinguish_bits(n)
                    row.update(run_one(cfg, n, seed, args))
                    append(args.out, row)
                    report(row)
                    if row["status"] != "ok":
                        stopped[cfg["config"]] = n
                        print(f"  -> {cfg['config']} stops at n = {n}")
                        break
    except KeyboardInterrupt:
        print("\ninterrupted; finished runs are saved in", args.out)


if __name__ == "__main__":
    main()
