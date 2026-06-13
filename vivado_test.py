"""Run generated designs through Vivado on a remote host up to block-design
validation (no synthesis), and report which ones validate.

For each seed this:
  1. generates the design locally with --no-synth,
  2. copies all designs to the remote host (rsync over ssh),
  3. runs `vivado -mode batch -source design.tcl` on each remotely, and
  4. checks the Vivado output for the RANDSOC_BD_VALIDATED_OK sentinel.

This is the Vivado-level counterpart to smoke_test.py: smoke_test checks that
the Tcl is generated; this checks that Vivado accepts and validates the design
(IP configuration, interface/width compatibility, connectivity) -- without
paying for synthesis.

Vivado runs remotely because that's where the toolchain and licenses live; the
default host is CCL1 (see ~/.ssh/config). Exit code is non-zero if any design
fails to validate.
"""

import argparse
import concurrent.futures
import pathlib
import shutil
import subprocess
import sys
import threading

DEFAULT_PART = "xc7a200tlffv1156-2L"
DEFAULT_CONFIG = "default_config.yaml"
DEFAULT_HOST = "CCL1"
DEFAULT_REMOTE_DIR = "randsoc_vivado_test"
DEFAULT_VIVADO = "/tools/Xilinx/Vivado/2024.2/bin/vivado"
SENTINEL = "RANDSOC_BD_VALIDATED_OK"
OUT_ROOT = pathlib.Path("temp/vivado_test")

# Live local `ssh` subprocesses, so Ctrl+C can terminate them, and a flag to
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


def open_master(host):
    """Pre-open a multiplex master connection so the parallel job connections
    reuse it (one auth, no MaxStartups handshake burst, and no 75-way race to
    create the master). Returns the master Popen, or None if it couldn't start.
    """
    try:
        proc = subprocess.Popen(
            ["ssh", "-N", "-o", "ControlMaster=auto", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    return proc


def close_master(host, master_proc):
    """Tear down the multiplex master connection."""
    subprocess.run(
        ["ssh", "-O", "exit", host],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if master_proc and master_proc.poll() is None:
        master_proc.terminate()


def shutdown_remote(host, remote_dir, timeout=30):
    """On interrupt, kill the remote Vivado jobs we launched. They are tagged via
    `-tclargs <remote_dir>`, so `pkill -f <remote_dir>` matches exactly our runs
    (both the wrapping shell and vivado) and nothing else on the shared host.
    """
    print(f"  killing remote Vivado jobs on {host}...")
    try:
        subprocess.run(
            ["ssh", host, f"pkill -u $USER -f {remote_dir}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.SubprocessError:
        pass


def terminate_local_procs():
    """Terminate all in-flight local ssh subprocesses."""
    with _live_lock:
        procs = list(_live_procs)
    for proc in procs:
        if proc.poll() is None:
            proc.terminate()


def generate(seed, config, part):
    """Generate one design locally with --no-synth. Returns (ok, last_error)."""
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
            "--no-synth",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return True, ""
    lines = [l for l in proc.stderr.strip().splitlines() if l.strip()]
    return False, lines[-1] if lines else f"exit {proc.returncode}"


def run_remote(seed, host, remote_dir, vivado, timeout):
    """Run Vivado validation for one seed on the remote host.

    Returns (ok, detail). Success is determined by the sentinel appearing in the
    Vivado console output; on failure we surface the first ERROR line.

    The vivado invocation is tagged with `-tclargs <remote_dir>` so a Ctrl+C
    cleanup can `pkill` exactly our jobs. We use Popen (not subprocess.run) so the
    local ssh client can be terminated on interrupt.
    """
    if _shutdown.is_set():
        return False, "cancelled"

    rel_dir = f"{remote_dir}/seed_{seed}"
    remote_cmd = (
        f"cd {rel_dir} && {vivado} -mode batch -nojournal "
        f"-log vivado.log -source design.tcl -tclargs {remote_dir}"
    )
    proc = subprocess.Popen(
        ["ssh", host, remote_cmd],
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
    if SENTINEL in output:
        return True, ""

    errors = [
        l.strip()
        for l in output.splitlines()
        if l.startswith("ERROR:") or "CRITICAL WARNING:" in l
    ]
    if errors:
        return False, errors[0]
    return False, f"no sentinel (vivado exit {proc.returncode})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--num", type=int, default=30, help="Number of designs")
    parser.add_argument("--start", type=int, default=0, help="First seed")
    parser.add_argument("--part", default=DEFAULT_PART, help="Xilinx part name")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Creator config yaml")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Remote ssh host")
    parser.add_argument(
        "--remote-dir",
        default=DEFAULT_REMOTE_DIR,
        help="Remote working dir (relative to remote home)",
    )
    parser.add_argument("--vivado", default=DEFAULT_VIVADO, help="Remote vivado path")
    parser.add_argument(
        "--jobs", type=int, default=75, help="Parallel remote Vivado runs"
    )
    parser.add_argument(
        "--timeout", type=int, default=900, help="Per-design Vivado timeout (s)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="Keep local output dirs (default: remove)"
    )
    args = parser.parse_args()

    seeds = list(range(args.start, args.start + args.num))

    # 1. Generate all designs locally (--no-synth)
    if not args.keep and OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.num} designs locally (--no-synth)...")
    gen_failures = []
    with concurrent.futures.ThreadPoolExecutor() as pool:
        futs = {pool.submit(generate, s, args.config, args.part): s for s in seeds}
        for fut in concurrent.futures.as_completed(futs):
            ok, err = fut.result()
            if not ok:
                seed = futs[fut]
                gen_failures.append((seed, err))
                print(f"  seed {seed:>4}  GEN-FAIL  {err}")
    if gen_failures:
        print(f"\n{len(gen_failures)} design(s) failed to generate; aborting.")
        return 1

    # 2. Copy designs to the remote host
    print(f"Copying designs to {args.host}:{args.remote_dir}/ ...")
    rsync = subprocess.run(
        [
            "rsync",
            "-az",
            "--delete",
            f"{OUT_ROOT}/",
            f"{args.host}:{args.remote_dir}/",
        ],
        capture_output=True,
        text=True,
    )
    if rsync.returncode != 0:
        print(f"rsync failed:\n{rsync.stderr}")
        return 1

    # 3. Run Vivado validation remotely, with a live progress bar
    print(
        f"Running Vivado validation on {args.host} "
        f"({args.jobs} parallel)...\n"
    )

    # Pre-open the multiplex master so all job connections reuse it (avoids a
    # 75-way race to create it, and the MaxStartups handshake burst).
    master_proc = open_master(args.host)

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
            run_remote, s, args.host, args.remote_dir, args.vivado, args.timeout
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
                # Clear the bar, print the status line above it, redraw the bar
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
        shutdown_remote(args.host, args.remote_dir)
        close_master(args.host, master_proc)
        print(f"  {done}/{total} finished before interrupt; remote jobs killed.")
        return 130
    finally:
        if not interrupted:
            executor.shutdown(wait=True)
            close_master(args.host, master_proc)

    if is_tty:
        sys.stdout.write("\n")
        sys.stdout.flush()

    # 4. Report
    results.sort()
    failures = [(s, d) for s, ok, d in results if not ok]
    passed = len(results) - len(failures)
    print(f"\n{passed}/{len(results)} designs validated in Vivado.")
    if failures:
        by_error = {}
        for seed, detail in failures:
            by_error.setdefault(detail, []).append(seed)
        print("\nFailures by error:")
        for detail, fseeds in sorted(by_error.items(), key=lambda kv: -len(kv[1])):
            seed_list = ", ".join(str(s) for s in fseeds)
            print(f"  [{len(fseeds)}] {detail}\n        seeds: {seed_list}")
        print(
            f"\nVivado logs are on {args.host} under "
            f"{args.remote_dir}/seed_<n>/vivado.log"
        )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
