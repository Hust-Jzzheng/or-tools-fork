# MiniZinc Challenge 2026 benchmark harness

This harness runs the official MiniZinc Challenge 2026 model/instance archive against an OR-Tools CP-SAT FlatZinc binary. It is intended for a controlled **12-worker, 1800-second-per-instance** comparison between the upstream v9.15 baseline and `cpsat-enhanced-v9.15`.

## Dataset

The manifest pins the MiniZinc archive repository and commit. It contains 20 models and 100 model/data pairs (70 `.dzn` and 30 `.json` files). Do not silently update the manifest when comparing builds; change the pinned commit only as a deliberate benchmark-version change.

```bash
git clone https://github.com/MiniZinc/mzn-challenge.git ../mzn-challenge
git -C ../mzn-challenge checkout 7639931e89b6b8bba48ef129d52fba866bc36702
```

Use MiniZinc **2.9.7**, matching the 2026 challenge toolchain. The official challenge runs 100 instances and its published PAR/OPEN execution profile uses 8 cores; this harness deliberately uses the requested 12 workers and 1800 seconds instead.

## Build both binaries

Use Bazel **8.5.0** for the OR-Tools 9.15 dependency set. Bazel 9.x removes the legacy `CcInfo` symbol used by the pinned `rules_go` dependency, so do not use the latest Bazel with this tag without updating dependencies.

```bash
git fetch --tags origin
bash benchmarks/minizinc2026/build_both.sh
```

The script creates detached Git worktrees and builds `//ortools/flatzinc:fz` with `--compilation_mode=opt`. It places both binaries in `../or-tools-fork-build/minizinc2026/bin/`.

## Run baseline and enhanced

```bash
python3 benchmarks/minizinc2026/run_benchmark.py \
  --dataset-root ../mzn-challenge \
  --repo-root ../or-tools-fork-build/minizinc2026/worktrees/v9.15 \
  --fz-bin ../or-tools-fork-build/minizinc2026/bin/fz-v9.15 \
  --results-dir results/minizinc2026-baseline \
  --threads 12 --time-limit 1800 --seed 1

python3 benchmarks/minizinc2026/run_benchmark.py \
  --dataset-root ../mzn-challenge \
  --repo-root ../or-tools-fork-build/minizinc2026/worktrees/cpsat-enhanced-v9.15 \
  --fz-bin ../or-tools-fork-build/minizinc2026/bin/fz-cpsat-enhanced-v9.15 \
  --results-dir results/minizinc2026-enhanced \
  --threads 12 --time-limit 1800 --seed 1
```

For a quick smoke test, add `--limit 3`. To rerun an existing result directory, add `--no-resume`. The script runs instances sequentially using the 2026 PAR-style invocation (`-i --output-mode dzn --output-objective -p 12`), with 12 CP-SAT workers per instance. The 1800-second outer wall-clock limit includes MiniZinc flattening; the same limit is also passed to the solver internally.

Each instance gets `stdout.log`, `stderr.log`, and `result.json`; the aggregate `summary.csv` is rewritten after each instance. Compare baseline and enhanced using the same CPU, memory limit, OS, MiniZinc version, seed, and dataset commit.

## Important interpretation

The MiniZinc 2026 archive is not a single `.mzn` file: each of the 20 models is paired with five data files. The manifest preserves those pairs. Do not compare only solved count; also compare objective quality, proof status, wall time, and per-instance regressions. The runner records raw logs so parsing can be improved without rerunning expensive instances.

The harness does not claim a performance gain by itself. The gain must be measured after the modified solver passes correctness and compilation tests.

## Compare two result directories

```bash
python3 benchmarks/minizinc2026/compare_results.py \
  --baseline results/minizinc2026-baseline/summary.csv \
  --enhanced results/minizinc2026-enhanced/summary.csv \
  --output results/minizinc2026-comparison.csv
```

The comparison checks that the dataset commit, MiniZinc version, thread count,
time limit, and seed match. It reports terminal/feasible/proven counts, PAR-2
scores, geometric-mean speedup on jointly completed instances, and per-instance
status/time/objective/bound differences. It does not assume whether a model is
minimization or maximization when comparing raw objective values.
