"""Quick smoke test: generate many random designs through the Tcl creation
stage (no Vivado) and report which seeds succeed.

This is a fast first-pass check while developing new IP. It does NOT run Vivado;
it only verifies that `main.py` can build a design and write out its Tcl for a
range of random seeds.

Usage:
    python smoke_test.py [-n NUM] [--start SEED] [--part PART] [--config CONFIG]
                         [--jobs N] [--keep]

Exit code is non-zero if any design fails.
"""

import argparse
import concurrent.futures
import pathlib
import shutil
import subprocess
import sys

DEFAULT_PART = "xc7a200tlffv1156-2L"
DEFAULT_CONFIG = "configs/default.yaml"
OUT_ROOT = pathlib.Path("temp/smoke")


def run_one(seed, config, part):
    """Build a single design in its own dir. Returns (seed, ok, last_error_line)."""
    out_dir = OUT_ROOT / f"seed_{seed}"
    proc = subprocess.run(
        [
            sys.executable,
            "main.py",
            str(out_dir),
            config,
            "--seed",
            str(seed),
            "--part",
            part,
        ],
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    last_error = ""
    if not ok:
        # Surface the most useful one-line summary: the final traceback line.
        lines = [l for l in proc.stderr.strip().splitlines() if l.strip()]
        last_error = lines[-1] if lines else f"exit code {proc.returncode}"
    return seed, ok, last_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--num", type=int, default=30, help="Number of designs")
    parser.add_argument("--start", type=int, default=0, help="First seed")
    parser.add_argument("--part", default=DEFAULT_PART, help="Xilinx part name")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Creator config yaml")
    parser.add_argument("--jobs", type=int, default=0, help="Parallel jobs (0 = auto)")
    parser.add_argument(
        "--keep", action="store_true", help="Keep output dirs (default: remove first)"
    )
    args = parser.parse_args()

    if not args.keep and OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    seeds = range(args.start, args.start + args.num)
    jobs = args.jobs or None  # None lets the pool pick a sensible default

    print(f"Building {args.num} designs (seeds {seeds.start}..{seeds.stop - 1}) "
          f"for part {args.part}...\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(run_one, s, args.config, args.part): s for s in seeds}
        for future in concurrent.futures.as_completed(futures):
            seed, ok, last_error = future.result()
            results.append((seed, ok, last_error))
            status = "PASS" if ok else "FAIL"
            line = f"  seed {seed:>4}  {status}"
            if not ok:
                line += f"  {last_error}"
            print(line)

    results.sort()
    failures = [(s, e) for s, ok, e in results if not ok]
    passed = len(results) - len(failures)

    print(f"\n{passed}/{len(results)} designs passed Tcl creation.")
    if failures:
        # Group failing seeds by their error message for a quick triage view.
        by_error = {}
        for seed, err in failures:
            by_error.setdefault(err, []).append(seed)
        print("\nFailures by error:")
        for err, fseeds in sorted(by_error.items(), key=lambda kv: -len(kv[1])):
            seed_list = ", ".join(str(s) for s in fseeds)
            print(f"  [{len(fseeds)}] {err}\n        seeds: {seed_list}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
