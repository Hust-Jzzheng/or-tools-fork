#!/usr/bin/env bash
set -euo pipefail
REF="${1:-cpsat-enhanced-v9.15}"
ROOT="$(git rev-parse --show-toplevel)"
OUT="${2:-${ROOT}/build/minizinc2026}"
SAFE_REF="${REF//\//_}"
WORKTREE="${OUT}/worktrees/${SAFE_REF}"
BIN_DIR="${OUT}/bin"
mkdir -p "${OUT}/worktrees" "${BIN_DIR}"
if [[ ! -e "${WORKTREE}/.git" ]]; then
  git -C "${ROOT}" worktree add --detach "${WORKTREE}" "${REF}"
fi
(
  cd "${WORKTREE}"
  bazel build --config=opt //ortools/flatzinc:fz
  cp bazel-bin/ortools/flatzinc/fz "${BIN_DIR}/fz-${SAFE_REF}"
)
echo "Built: ${BIN_DIR}/fz-${SAFE_REF}"
