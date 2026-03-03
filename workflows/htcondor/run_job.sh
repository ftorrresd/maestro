#!/usr/bin/env bash
set -euo pipefail

CONFIG_SOURCE="$1"
python skim.py "${CONFIG_SOURCE}"
