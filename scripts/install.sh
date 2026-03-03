#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

VENV_DIR=".venv"
REQ_FILE="requirements.txt"

if [[ "${1:-}" == "--dev" ]]; then
	REQ_FILE="requirements-dev.txt"
fi

python -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${REQ_FILE}"

echo "Installed dependencies from ${REQ_FILE} in ${VENV_DIR}."
echo "Activate with: source ${VENV_DIR}/bin/activate"
