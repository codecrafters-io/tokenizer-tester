#!/bin/sh
# Reference solution. The tester invokes this when CODECRAFTERS_REPOSITORY_DIR
# points at this directory.
set -e
DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
REF="$DIR/../scenarios/base/tokenizer.py"
VENV="$DIR/../../../.venv/bin/python"
if [ -x "$VENV" ]; then
  exec "$VENV" "$REF" "$@"
fi
exec python3 "$REF" "$@"
