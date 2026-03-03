#!/usr/bin/env bash
set -euo pipefail

TASK_FILE="${1:-workflows/gnu_parallel/tasks.txt}"
JOBS="${2:-8}"

parallel --bar --jobs "${JOBS}" <"${TASK_FILE}"
