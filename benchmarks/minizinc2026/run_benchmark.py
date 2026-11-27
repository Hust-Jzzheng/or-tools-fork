#!/usr/bin/env python3
"""Run pinned MiniZinc Challenge 2026 instances with an OR-Tools CP-SAT FlatZinc binary."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SOLVER_ID = "org.minizinc.or-tools-cpsat-enhanced"
STAT_RE = re.compile(r"%%%mzn-stat:\s*([^=\s]+)=(.*)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_stats(output: str) -> dict[str, str]:
    stats: dict[str, str] = {}
    for line in output.splitlines():
        match = STAT_RE.search(line)
        if match:
            stats[match.group(1)] = match.group(2).strip()
    return stats


def classify(output: str, return_code: int, timed_out: bool) -> tuple[str, bool]:
    has_solution = (
        "----------" in output
        or "=====SATISFIABLE=====" in output
        or "=====OPTIMAL=====" in output
    )
    if "=====OPTIMAL=====" in output:
        return "OPTIMAL", True
    if "=====UNSATISFIABLE=====" in output:
        return "UNSAT", False
    if "=====SATISFIABLE=====" in output:
        return "FEASIBLE", True
    if timed_out:
        return "TIMEOUT", has_solution
    if "=====ERROR=====" in output or return_code != 0:
        return "ERROR", has_solution
    # With MiniZinc's -i option, FlatZinc may print one or more solutions
    # followed by the standard separator but no final SATISFIABLE marker.
    # Such a clean process exit is a feasible result, not UNKNOWN.
    if has_solution:
        return "FEASIBLE", True
    if "=====UNKNOWN=====" in output:
        return "UNKNOWN", False
    return "UNKNOWN", False


def terminate_process_group(proc: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def run_one(item: dict[str, str], dataset_root: Path, minizinc: str,
            minizinc_version: str, dataset_commit: str,
            solver_binary_sha256: str, env: dict[str, str], output_dir: Path,
            threads: int, time_limit: int, seed: int, resume: bool) -> dict[str, Any]:
    instance_id = item["id"]
    safe_id = instance_id.replace("/", "__").replace("\\", "__")
    instance_dir = output_dir / safe_id
    instance_dir.mkdir(parents=True, exist_ok=True)
    result_path = instance_dir / "result.json"
    stdout_path = instance_dir / "stdout.log"
    stderr_path = instance_dir / "stderr.log"

    if resume and result_path.exists():
        try:
            previous = json.loads(result_path.read_text(encoding="utf-8"))
            if (
                previous.get("complete") is True
                and previous.get("dataset_commit") == dataset_commit
                and previous.get("solver_binary_sha256") == solver_binary_sha256
                and previous.get("threads") == threads
                and previous.get("time_limit_seconds") == time_limit
                and previous.get("seed") == seed
                and previous.get("minizinc_version") == minizinc_version
            ):
                print(f"[SKIP] {instance_id}: matching completed result exists", flush=True)
                return previous
        except (OSError, json.JSONDecodeError):
            pass

    model_path = dataset_root / item["model"]
    data_path = dataset_root / item["data"]
    if not model_path.is_file() or not data_path.is_file():
        raise FileNotFoundError(f"Missing model/data for {instance_id}: {model_path}, {data_path}")

    # MiniZinc -t is milliseconds; -p maps to OR-Tools FlatZinc --threads.
    command = [
        minizinc, "--solver", SOLVER_ID,
        "-i", "--output-mode", "dzn", "--output-objective",
        "-s", "-p", str(threads), "-r", str(seed),
        "-t", str(time_limit * 1000), str(model_path), str(data_path),
    ]
    print(f"[RUN] {instance_id} | threads={threads} | wall_limit={time_limit}s", flush=True)
    start = time.monotonic()
    timed_out = False
    return_code = -1
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, \
         stderr_path.open("w", encoding="utf-8", errors="replace") as stderr_file:
        proc = subprocess.Popen(
            command, cwd=dataset_root, env=env, stdout=stdout_file,
            stderr=stderr_file, text=True, start_new_session=(os.name != "nt"),
        )
        try:
            return_code = proc.wait(timeout=time_limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_group(proc)
            return_code = 124

    wall_time = time.monotonic() - start
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    status, has_solution = classify(stdout + "\n" + stderr, return_code, timed_out)
    stats = parse_stats(stdout + "\n" + stderr)
    result: dict[str, Any] = {
        "complete": True, "instance_id": instance_id, "model": item["model"],
        "data": item["data"], "threads": threads, "time_limit_seconds": time_limit,
        "seed": seed, "minizinc_version": minizinc_version,
        "dataset_commit": dataset_commit,
        "solver_binary_sha256": solver_binary_sha256,
        "wall_time_seconds": round(wall_time, 3),
        "return_code": return_code, "timed_out": timed_out, "status": status,
        "has_solution": has_solution, "solver_stats": stats, "command": command,
        "stdout_log": str(stdout_path), "stderr_log": str(stderr_path),
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] {instance_id}: {status}, {wall_time:.1f}s", flush=True)
    return result


def write_summary(output_dir: Path, results: list[dict[str, Any]]) -> None:
    fields = [
        "instance_id", "status", "has_solution", "wall_time_seconds",
        "threads", "time_limit_seconds", "seed", "return_code", "timed_out",
        "flatTime", "solveTime", "objective", "objectiveBound",
        "boolVariables", "nodes", "failures", "propagations",
        "model", "data", "minizinc_version", "dataset_commit",
        "solver_binary_sha256",
    ]
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            row = dict(result)
            row.update(result.get("solver_stats", {}))
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--fz-bin", required=True, type=Path)
    parser.add_argument("--minizinc", default="minizinc")
    parser.add_argument("--expected-minizinc-version", default="2.9.7")
    parser.add_argument("--allow-version-mismatch", action="store_true")
    parser.add_argument("--allow-dataset-mismatch", action="store_true")
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--time-limit", type=int, default=1800,
                        help="Total wall-clock seconds per instance, including flattening")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--instances", default="", help="Comma-separated exact instance IDs")
    parser.add_argument("--limit", type=int, default=0, help="Run first N selected instances")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    repo_root = args.repo_root.resolve()
    fz_bin = args.fz_bin.resolve()
    results_dir = args.results_dir.resolve()
    manifest = json.loads(Path(__file__).with_name("manifest.json").read_text(encoding="utf-8"))

    if not dataset_root.is_dir():
        parser.error(f"dataset root does not exist: {dataset_root}")
    expected_dataset_commit = manifest["dataset"]["commit"]
    dataset_git = subprocess.run(
        ["git", "-C", str(dataset_root), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=False,
    )
    actual_dataset_commit = dataset_git.stdout.strip()
    if dataset_git.returncode != 0:
        parser.error(f"dataset root must be a Git checkout at {expected_dataset_commit}")
    if (actual_dataset_commit != expected_dataset_commit
            and not args.allow_dataset_mismatch):
        parser.error(
            f"expected MiniZinc archive commit {expected_dataset_commit}, "
            f"got {actual_dataset_commit}; use --allow-dataset-mismatch only for smoke tests"
        )
    if not fz_bin.is_file():
        parser.error(f"FlatZinc binary does not exist: {fz_bin}")
    mznlib = repo_root / "ortools" / "flatzinc" / "mznlib"
    if not mznlib.is_dir():
        parser.error(f"OR-Tools FlatZinc MiniZinc library does not exist: {mznlib}")
    if args.threads < 1 or args.time_limit < 1:
        parser.error("--threads and --time-limit must be positive")

    selected = manifest["instances"]
    if args.instances:
        wanted = {x.strip() for x in args.instances.split(",") if x.strip()}
        selected = [x for x in selected if x["id"] in wanted]
        missing = wanted - {x["id"] for x in selected}
        if missing:
            parser.error(f"unknown instance IDs: {sorted(missing)}")
    if args.limit > 0:
        selected = selected[:args.limit]

    solver_binary_sha256 = sha256_file(fz_bin)
    solver_dir = results_dir / "solver-config"
    solver_dir.mkdir(parents=True, exist_ok=True)
    solver_config = {
        "id": SOLVER_ID, "name": "OR-Tools CP-SAT Enhanced",
        "version": "9.15-enhanced",
        "description": "OR-Tools CP-SAT FlatZinc backend built from selected source tree",
        "mznlib": str(mznlib.resolve()), "executable": str(fz_bin),
        "tags": ["cp-sat", "cp", "lcg", "int"],
        "stdFlags": ["-a", "-i", "-f", "-p", "-r", "-s", "-v"],
        "extraFlags": [
            ["--params", "Provide parameters interpreted as a text SatParameters proto", "string", ""],
            ["--fz_int_max", "Provide the maximum value for integer variables", "int", "1125899906842624"],
        ],
        "supportsMzn": False, "supportsFzn": True, "needsSolns2Out": True,
        "needsMznExecutable": False, "needsStdlibDir": False, "isGUIApplication": False,
    }
    (solver_dir / "or-tools-cpsat-enhanced.msc").write_text(
        json.dumps(solver_config, indent=2) + "\n", encoding="utf-8"
    )
    env = os.environ.copy()
    old_solver_path = env.get("MZN_SOLVER_PATH", "")
    env["MZN_SOLVER_PATH"] = str(solver_dir) + (os.pathsep + old_solver_path if old_solver_path else "")

    version_check = subprocess.run(
        [args.minizinc, "--version"], cwd=dataset_root, env=env,
        text=True, capture_output=True, check=False,
    )
    minizinc_version = (version_check.stdout + version_check.stderr).strip()
    if version_check.returncode != 0:
        parser.error(f"could not execute MiniZinc: {minizinc_version}")
    if (args.expected_minizinc_version not in minizinc_version
            and not args.allow_version_mismatch):
        parser.error(
            f"expected MiniZinc {args.expected_minizinc_version}, got: {minizinc_version}; "
            "use --allow-version-mismatch only for non-comparable smoke tests"
        )

    check = subprocess.run(
        [args.minizinc, "--solvers"], cwd=dataset_root, env=env,
        text=True, capture_output=True, check=False,
    )
    if check.returncode != 0 or SOLVER_ID not in check.stdout:
        sys.stderr.write(check.stdout + "\n" + check.stderr)
        parser.error(f"MiniZinc could not discover solver {SOLVER_ID}; check MZN_SOLVER_PATH and .msc")

    results_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"Dataset commit: {manifest['dataset']['commit']}\n"
        f"Selected instances: {len(selected)}\n"
        f"Solver: {fz_bin}\nBinary SHA256: {solver_binary_sha256}\n"
        f"MiniZinc: {minizinc_version}\n"
        f"Threads: {args.threads}; wall limit: {args.time_limit}s; seed: {args.seed}",
        flush=True,
    )
    if args.dry_run:
        for item in selected:
            print(f"{item['id']}: {item['model']} + {item['data']}")
        return 0

    results: list[dict[str, Any]] = []
    for item in selected:
        result = run_one(
            item, dataset_root, args.minizinc, minizinc_version,
            expected_dataset_commit, solver_binary_sha256, env, results_dir,
            args.threads, args.time_limit, args.seed, not args.no_resume,
        )
        results.append(result)
        write_summary(results_dir, results)
    print(f"Summary written to {results_dir / 'summary.csv'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
