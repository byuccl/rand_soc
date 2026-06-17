"""Run generated designs through Vivado up to block-design validation (no
synthesis by default), and report which ones validate.

For each seed this:
  1. generates the design locally with --no-synth, and
  2. runs `vivado -mode batch -source design.tcl` locally on each design.
  3. checks the Vivado output for the RANDSOC_BD_VALIDATED_OK sentinel.

This is the Vivado-level counterpart to smoke_test.py: smoke_test checks that
the Tcl is generated; this checks that Vivado accepts and validates the design
(IP configuration, interface/width compatibility, connectivity) -- without
paying for synthesis.

Exit code is non-zero if any design fails to validate.
"""

import argparse
import concurrent.futures
import pathlib
import shutil
import subprocess
import sys
import threading

DEFAULT_PART = "xc7a200tlffv1156-2L"
DEFAULT_CONFIG = "configs/default.yaml"
DEFAULT_VIVADO = "/tools/Xilinx/Vivado/2024.2/bin/vivado"
SENTINEL = "RANDSOC_BD_VALIDATED_OK"
DCP_MARKER = "RANDSOC_SYNTH_DCP_OK"
DCP_NAME = "synth.dcp"
OUT_ROOT = pathlib.Path("temp/vivado_test")

# Live local Vivado subprocesses, so Ctrl+C can terminate them, and a flag to
# stop launching new work once we're shutting down.
_live_procs = set()
_live_lock = threading.Lock()
_shutdown = threading.Event()


def _bar(done, total, valid, width=30):
    """Render a text progress bar string."""
    filled = int(width * done / total) if total else width
    fail = done - valid
    return (
        f"[{'#' * filled}{'-' * (width - filled)}] "
        f"{done}/{total}  valid={valid} fail={fail}"
    )


def terminate_local_procs():
    """Terminate all in-flight local Vivado subprocesses."""
    with _live_lock:
        procs = list(_live_procs)
    for proc in procs:
        if proc.poll() is None:
            proc.terminate()


def generate(seed, config, part, synth=False):
    """Generate one design locally. With synth=False the Tcl stops after
    block-design validation (--no-synth); with synth=True it runs full
    synthesis. Returns (ok, last_error)."""
    out_dir = OUT_ROOT / f"seed_{seed}"
    cmd = [
        sys.executable,
        "main.py",
        str(out_dir),
        config,
        "--seed",
        str(seed),
        "--part",
        part,
    ]
    if not synth:
        cmd.append("--no-synth")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return True, ""
    lines = [l for l in proc.stderr.strip().splitlines() if l.strip()]
    return False, lines[-1] if lines else f"exit {proc.returncode}"


def run_local(seed, vivado, timeout, synth=False):
    """Run Vivado for one seed on the local machine.

    Returns (ok, detail). In validation mode (synth=False) success is the
    RANDSOC_BD_VALIDATED_OK sentinel in the Vivado console output. In synth
    mode success is the existence of synth.dcp after Vivado exits and no ERROR
    lines in the output. On failure we surface the first ERROR line.
    """
    if _shutdown.is_set():
        return False, "cancelled"

    local_dir = OUT_ROOT / f"seed_{seed}"
    cmd = [
        vivado, "-mode", "batch", "-nojournal",
        "-log", "vivado.log", "-source", "design.tcl",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(local_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    with _live_lock:
        _live_procs.add(proc)
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return False, f"timeout after {timeout}s"
    finally:
        with _live_lock:
            _live_procs.discard(proc)

    if _shutdown.is_set():
        return False, "cancelled"

    output = output or ""
    try:
        (local_dir / "vivado_output.log").write_text(output)
    except OSError:
        pass

    lines = [l.strip() for l in output.splitlines()]
    errors = [
        l
        for l in lines
        if l.startswith("ERROR:") and "due to earlier errors" not in l
    ]

    if synth:
        dcp_ok = (local_dir / DCP_NAME).exists()
        if dcp_ok and not errors:
            return True, ""
        if errors:
            return False, errors[0]
        crit = [l for l in lines if "CRITICAL WARNING:" in l]
        if crit:
            return False, crit[0]
        return False, f"no {DCP_NAME} produced (vivado exit {proc.returncode})"

    if SENTINEL in output:
        return True, ""
    if errors:
        return False, errors[0]
    crit = [l for l in lines if "CRITICAL WARNING:" in l]
    if crit:
        return False, crit[0]
    return False, f"no sentinel (vivado exit {proc.returncode})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--num", type=int, default=30, help="Number of designs")
    parser.add_argument("--start", type=int, default=0, help="First seed")
    parser.add_argument("--part", default=DEFAULT_PART, help="Xilinx part name")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Creator config yaml")
    parser.add_argument("--vivado", default=DEFAULT_VIVADO, help="Path to vivado binary")
    parser.add_argument(
        "--jobs", type=int, default=4, help="Parallel Vivado runs"
    )
    parser.add_argument(
        "--timeout", type=int, default=900, help="Per-design Vivado timeout (s)"
    )
    parser.add_argument(
        "--synth",
        action="store_true",
        help="Run full synthesis and pass only if synth.dcp is produced "
        "(default: stop after block-design validation)",
    )
    parser.add_argument(
        "--keep", action="store_true", help="Keep local output dirs (default: remove)"
    )
    args = parser.parse_args()

    seeds = list(range(args.start, args.start + args.num))

    # 1. Generate all designs locally
    if not args.keep and OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    mode = "synthesis" if args.synth else "--no-synth"
    print(f"Generating {args.num} designs locally ({mode})...")
    gen_failures = []
    with concurrent.futures.ThreadPoolExecutor() as pool:
        futs = {
            pool.submit(generate, s, args.config, args.part, args.synth): s
            for s in seeds
        }
        for fut in concurrent.futures.as_completed(futs):
            ok, err = fut.result()
            if not ok:
                seed = futs[fut]
                gen_failures.append((seed, err))
                print(f"  seed {seed:>4}  GEN-FAIL  {err}")
    if gen_failures:
        print(f"\n{len(gen_failures)} design(s) failed to generate; aborting.")
        return 1

    # 2. Run Vivado locally, with a live progress bar
    action = "synthesis" if args.synth else "validation"
    print(f"Running Vivado {action} locally ({args.jobs} parallel)...\n")

    is_tty = sys.stdout.isatty()
    total = len(seeds)
    done = valid = 0
    results = []

    if is_tty:
        sys.stdout.write(_bar(done, total, valid))
        sys.stdout.flush()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs)
    futs = {
        executor.submit(
            run_local,
            s,
            args.vivado,
            args.timeout,
            args.synth,
        ): s
        for s in seeds
    }
    interrupted = False
    try:
        for fut in concurrent.futures.as_completed(futs):
            seed = futs[fut]
            ok, detail = fut.result()
            results.append((seed, ok, detail))
            done += 1
            valid += 1 if ok else 0

            status = "VALID" if ok else "FAIL"
            line = f"  seed {seed:>4}  {status}"
            if not ok:
                short = detail if len(detail) <= 70 else detail[:69] + "..."
                line += f"  {short}"

            if is_tty:
                sys.stdout.write("\r\033[K" + line + "\n" + _bar(done, total, valid))
                sys.stdout.flush()
            else:
                print(line, flush=True)
    except KeyboardInterrupt:
        interrupted = True
        _shutdown.set()
        if is_tty:
            sys.stdout.write("\n")
            sys.stdout.flush()
        print("\nInterrupted -- shutting down cleanly:")
        terminate_local_procs()
        executor.shutdown(wait=False, cancel_futures=True)
        print(f"  {done}/{total} finished before interrupt; local Vivado jobs killed.")
        return 130
    finally:
        if not interrupted:
            executor.shutdown(wait=True)

    if is_tty:
        sys.stdout.write("\n")
        sys.stdout.flush()

    # 3. Report (to console and to a local results.log)
    results.sort()
    failures = [(s, d) for s, ok, d in results if not ok]
    passed = len(results) - len(failures)

    verb = "synthesized" if args.synth else "validated"
    lines = [f"{passed}/{len(results)} designs {verb} in Vivado.", ""]
    for seed, ok, detail in results:
        lines.append(f"  seed {seed:>4}  {'VALID' if ok else 'FAIL'}"
                     + ("" if ok else f"  {detail}"))
    if failures:
        by_error = {}
        for seed, detail in failures:
            by_error.setdefault(detail, []).append(seed)
        lines.append("\nFailures by error:")
        for detail, fseeds in sorted(by_error.items(), key=lambda kv: -len(kv[1])):
            seed_list = ", ".join(str(s) for s in fseeds)
            lines.append(f"  [{len(fseeds)}] {detail}\n        seeds: {seed_list}")
        lines.append(
            "\nPer-design Vivado output saved locally at "
            f"{OUT_ROOT}/seed_<n>/vivado_output.log"
        )

    report = "\n".join(lines)
    print("\n" + report)
    try:
        (OUT_ROOT / "results.log").write_text(report + "\n")
        print(f"\nSummary written to {OUT_ROOT}/results.log")
    except OSError:
        pass

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
