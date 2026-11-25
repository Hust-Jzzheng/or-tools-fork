#!/usr/bin/env bash
set -euo pipefail
REF="${1:-cpsat-enhanced-v9.15}"
ROOT="$(git rev-parse --show-toplevel)"
OUT="${2:-${ROOT}/build/minizinc2026}"
SAFE_REF="${REF//\//_}"
WORKTREE="${OUT}/worktrees/${SAFE_REF}"
BIN_DIR="${OUT}/bin"
mkdir -p "${OUT}/worktrees" "${BIN_DIR}"
BAZEL_VERSION="$(bazel --version | awk '{print $2}')"
if [[ "${BAZEL_VERSION}" != "8.5.0" ]]; then
  echo "Expected Bazel 8.5.0, found ${BAZEL_VERSION}" >&2
  exit 1
fi
EXPECTED_COMMIT="$(git -C "${ROOT}" rev-parse "${REF}^{commit}")"
if [[ -e "${WORKTREE}/.git" ]]; then
  ACTUAL_COMMIT="$(git -C "${WORKTREE}" rev-parse HEAD)"
  if [[ "${ACTUAL_COMMIT}" != "${EXPECTED_COMMIT}" ]]; then
    git -C "${ROOT}" worktree remove --force "${WORKTREE}"
  fi
fi
if [[ ! -e "${WORKTREE}/.git" ]]; then
  git -C "${ROOT}" worktree add --detach "${WORKTREE}" "${REF}"
fi
(
  cd "${WORKTREE}"
  bazel build --compilation_mode=opt //ortools/flatzinc:fz
  cp bazel-bin/ortools/flatzinc/fz "${BIN_DIR}/fz-${SAFE_REF}"
)
echo "Built: ${BIN_DIR}/fz-${SAFE_REF}"
