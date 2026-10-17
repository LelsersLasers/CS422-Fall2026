#!/usr/bin/env bash
set -euo pipefail

assignment_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
image="cs422-assignment2"
action="${1:-}"
if (( $# )); then shift; fi

case "$action" in
  build)
    exec docker build -t "$image" "$assignment_dir" "$@"
    ;;
  run)
    mkdir -p "$assignment_dir/output"
    exec docker run --rm --network host --user "$(id -u):$(id -g)" \
      -v "$assignment_dir/data:/app/data:ro" \
      -v "$assignment_dir/output:/app/output" \
      "$image" "$@"
    ;;
  *)
    echo "Usage: $0 {build|run} [arguments...]" >&2
    exit 2
    ;;
esac
