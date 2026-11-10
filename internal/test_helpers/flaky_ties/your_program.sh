#!/bin/sh
# A top-pair solution that answers ties correctly on the first run of each
# input and wrongly on every later run, like a program that picks among tied
# pairs by hash map iteration order. TestTieCasesRunMoreThanOnce expects the
# tester to reject it.
set -e
DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
REF="$DIR/../scenarios/flaky_ties/tokenizer.py"
VENV="$DIR/../../../.venv/bin/python"
if [ -x "$VENV" ]; then
  exec "$VENV" "$REF" "$@"
fi
exec python3 "$REF" "$@"
