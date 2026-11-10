"""top-pair that is right on the first run of an input and wrong after it.

Each run records the input in TOKENIZER_FLAKY_STATE_DIR. On a later run of
the same input, a tie goes to the last tied pair instead of the first.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "base"))

import tokenizer as reference  # noqa: E402


def main(argv):
    if argv[1] != "top-pair":
        raise SystemExit(f"flaky_ties only implements top-pair, got {argv[1]}")
    raw = Path(argv[2]).read_bytes()
    ids = json.loads(raw)

    state = Path(os.environ["TOKENIZER_FLAKY_STATE_DIR"]) / hashlib.sha256(raw).hexdigest()
    runs = int(state.read_text()) if state.exists() else 0
    state.write_text(str(runs + 1))

    stats = reference.get_stats(ids)
    best = max(stats.values())
    tied = [pair for pair in stats if stats[pair] == best]
    pair = tied[0] if runs == 0 else tied[-1]
    print(json.dumps(list(pair)))


if __name__ == "__main__":
    main(sys.argv)
