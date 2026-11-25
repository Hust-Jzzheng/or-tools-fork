#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/build_solver.sh" v9.15
"${SCRIPT_DIR}/build_solver.sh" cpsat-enhanced-v9.15
