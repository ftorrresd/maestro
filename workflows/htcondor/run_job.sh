#!/usr/bin/env bash
set -euo pipefail

CONFIG_SOURCE="$1"
maestro skim "${CONFIG_SOURCE}"
