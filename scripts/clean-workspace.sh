#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/clean-workspace.sh [--caches] [--artifacts] [--prefect] [--venv] [--all]

Safe default: removes only Python/pytest/ruff caches.

Options:
  --caches     Remove __pycache__/ + .pytest_cache/ + .ruff_cache/ (default)
  --artifacts  Remove artifacts/ and exports/
  --prefect    Remove .prefect-home/ (stops local Prefect state)
  --venv       Remove .venv/
  --all        Equivalent to --caches --artifacts --prefect --venv

Notes:
  - Does NOT delete .env.
  - Use Prefect server stop before --prefect.
EOF
}

do_caches=0
do_artifacts=0
do_prefect=0
do_venv=0

if [[ $# -eq 0 ]]; then
  do_caches=1
fi

for arg in "$@"; do
  case "$arg" in
    --caches) do_caches=1 ;;
    --artifacts) do_artifacts=1 ;;
    --prefect) do_prefect=1 ;;
    --venv) do_venv=1 ;;
    --all)
      do_caches=1
      do_artifacts=1
      do_prefect=1
      do_venv=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

if [[ $do_caches -eq 1 ]]; then
  rm -rf .pytest_cache .ruff_cache
  # Remove all __pycache__ dirs (globstar is bash-only).
  shopt -s globstar nullglob
  rm -rf **/__pycache__
fi

if [[ $do_artifacts -eq 1 ]]; then
  rm -rf artifacts exports
fi

if [[ $do_prefect -eq 1 ]]; then
  rm -rf .prefect-home
fi

if [[ $do_venv -eq 1 ]]; then
  rm -rf .venv
fi

echo "Workspace cleaned."
