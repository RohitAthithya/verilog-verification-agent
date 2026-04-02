#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(pwd)"

# Default: 32B model active
ln -sfn "$REPO_ROOT/models/qwen32b" "$REPO_ROOT/models/active/current"

# Lighter comparison model:
# ln -sfn "$REPO_ROOT/models/qwen14b" "$REPO_ROOT/models/active/current"

echo "Active model symlink now points to:"
readlink -f "$REPO_ROOT/models/active/current"
