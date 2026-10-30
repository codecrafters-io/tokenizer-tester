#!/usr/bin/env python3
"""Freeze expected stdout for every tokenizer stage.

Run from the tester repo with a Python that has `regex` and `tiktoken`:

    python3 scripts/generate_fixtures.py
"""

import json
import sys
from pathlib import Path

TESTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTER / "internal" / "test_helpers" / "scenarios" / "base"))

import tiktoken  # noqa: E402

import tokenizer as reference  # noqa: E402

OUT = TESTER / "internal" / "fixtures"
GPT2_DIR = OUT / "gpt2"
WAVE = "👋"


def case(name, args, files, expected, chunks=None):
    row = {"name": name, "args": args, "files": files, "expected": expected}
    if chunks is not None:
        row["chunks"] = chunks
    return row


def gpt2_chunks(text):
    return reference.GPT2_PAT.findall(text)


def write_stage(slug, cases):
    path = OUT / f"{slug}.json"
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{slug}: {len(cases)} cases")


def text_file(name, text):
    return {name: text}


def ids_file(ids):
    return {"ids.json": json.dumps(ids)}


def merges_file(merges, **extra):
    files = {"merges.json": json.dumps(merges)}
    files.update(extra)
    return files


def stage_bytes():
    samples = [
        ("wave-emoji", f"hi {WAVE}"),
        ("emoji-only", "🙂"),
        ("empty", ""),
        ("multiline", "one\ntwo\n"),
    ]
    cases = []
    for name, text in samples:
        cases.append(case(name, ["bytes", "text.txt"], text_file("text.txt", text), list(text.encode("utf-8"))))
    write_stage("utf8-bytes", cases)


def stage_top_pair():
    corpus = list("aaabdaaabac".encode())
    sequences = [
        ("visible", [1, 2, 3, 1, 2]),
        ("tie-first-pair-wins", [8, 9, 1, 2]),
        # (1, 2) and (3, 4) both appear twice. (3, 4) reaches 2 first, but
        # (1, 2) appears first.
        ("tie-first-occurrence", [1, 2, 3, 4, 3, 4, 1, 2]),
        # (5, 5) ties (8, 9) only when the overlapping (5, 5) counts.
        # No reversed pair is in this list, so treating (a, b) and (b, a)
        # as one pair still returns [5, 5].
        ("overlapping-pairs-count", [5, 5, 5, 8, 9, 8, 9]),
        # (2, 3) starts at index 1 and index 3. A stride of 2 never sees it.
        ("odd-offset-pair", [1, 2, 3, 2, 3]),
        # (1, 2) and (2, 1) are different pairs. (5, 6) is the top pair.
        ("order-matters", [1, 2, 9, 2, 1, 5, 6, 7, 5, 6]),
        # aaabdaaabac after its first merge. A 256 by 256 table cannot hold 256.
        ("ids-above-255", [256, 97, 98, 100, 256, 97, 98, 97, 99]),
        # Without a separator, (1, 12) and (11, 2) share the key "112".
        ("multi-digit-ids", [1, 12, 5, 11, 2, 6, 7, 8, 7, 8]),
        ("aaabdaaabac", corpus),
    ]
    cases = []
    for name, ids in sequences:
        cases.append(case(name, ["top-pair", "ids.json"], ids_file(ids), reference.top_pair(ids)))
    write_stage("top-pair", cases)


def stage_merge():
    corpus = list("aaabdaaabac".encode())
    specs = [
        ("visible", [1, 2, 3, 1, 2], 1, 2),
        ("aaa", [97, 97, 97], 97, 97),
        ("missing-pair", [1, 2, 3], 9, 9),
        ("aaabdaaabac", corpus, 97, 97),
        # Only the last two ids are (1, 2). A reversed match also merges (2, 1).
        # A string replace of "1,2" also matches inside 11.
        ("order-and-digits", [11, 2, 2, 1, 1, 2], 1, 2),
    ]
    cases = []
    for name, ids, left, right in specs:
        cases.append(
            case(
                name,
                ["merge", "ids.json", "--pair", f"{left},{right}"],
                ids_file(ids),
                reference.merge(ids, (left, right), 256),
            )
        )
    write_stage("apply-merge", cases)


def stage_train():
    paragraph = (
        "Byte pair encoding merges the most common pair. "
        "It keeps doing that until the vocabulary is large enough for the corpus.\n"
    )
    texts = {
        "visible": ("aaabdaaabac", 3),
        "six-merges": ("aaabdaaabac", 6),
        "hello-repeated": ("hello hello hello\n" * 4, 10),
        "fifty-merges": (paragraph * 3, 50),
        # é is the two bytes 195, 169. A UTF-16 code unit sees it as 233.
        "non-ascii": ("café café 👋👋\ncafé café 👋👋", 4),
    }
    cases = []
    for name, (text, count) in texts.items():
        expected = reference.train(text, count)
        if name == "non-ascii" and expected[-2:] != [[257, 195], [258, 169]]:
            raise SystemExit(f"{name} last merges {expected[-2:]}, want é's bytes")
        if count == 50 and len(expected) != 50:
            raise SystemExit(f"{name} produced {len(expected)} merges, want 50")
        cases.append(
            case(
                name,
                ["train", "corpus.txt", "--merges", str(count)],
                text_file("corpus.txt", text),
                expected,
            )
        )
    write_stage("train-bpe", cases)


def stage_encode():
    merges = reference.train("aaabdaaabac", 3)
    samples = [
        ("visible-aaab", "aaab"),
        ("training-corpus", "aaabdaaabac"),
        ("empty", ""),
    ]
    cases = []
    for name, text in samples:
        cases.append(
            case(
                name,
                ["encode", "text.txt", "--merges", "merges.json"],
                merges_file(merges, **text_file("text.txt", text)),
                reference.encode_text(text, merges),
            )
        )
    # (98, 98) is rank 0 and the most frequent pair. The leftmost pair is
    # (97, 98), so merging leftmost first produces [257, 256].
    leftmost_merges = [[98, 98], [97, 98]]
    cases.append(
        case(
            "leftmost-merge-first",
            ["encode", "text.txt", "--merges", "merges.json"],
            merges_file(leftmost_merges, **text_file("text.txt", "abbb")),
            reference.encode_text("abbb", leftmost_merges),
        )
    )
    # Both pairs occur twice. Rank order merges (98, 97) first. Recounting
    # frequency merges (97, 98) first and produces [257, 257, 97].
    rank_merges = [[98, 97], [97, 98]]
    cases.append(
        case(
            "rank-not-frequency",
            ["encode", "text.txt", "--merges", "merges.json"],
            merges_file(rank_merges, **text_file("text.txt", "ababa")),
            reference.encode_text("ababa", rank_merges),
        )
    )
    # é is bytes 195, 169. One merge of that pair leaves c, a, f, and the new id.
    cafe_merges = [[195, 169]]
    cases.append(
        case(
            "non-ascii",
            ["encode", "text.txt", "--merges", "merges.json"],
            merges_file(cafe_merges, **text_file("text.txt", "café")),
            reference.encode_text("café", cafe_merges),
        )
    )
    write_stage("encode", cases)


def stage_decode():
    merges = reference.train("aaabdaaabac", 3)
    specs = [
        ("visible", [258, 100], merges),
        ("half-wave", [240, 159], []),
        ("full-wave", [240, 159, 145, 139], []),
        ("two-invalid", [255, 255], []),
        # "hi"\ plus a newline. Hand-wrapped quotes do not escape these.
        ("json-escaping", [34, 104, 105, 34, 92, 10], []),
        # 256 is the first two bytes of 👋 and 257 is the last two.
        ("emoji-across-tokens", [256, 257], [[240, 159], [145, 139]]),
    ]
    cases = []
    for name, ids, merge_list in specs:
        cases.append(
            case(
                name,
                ["decode", "ids.json", "--merges", "merges.json"],
                merges_file(merge_list, **ids_file(ids)),
                reference.decode_ids(ids, merge_list),
            )
        )
    write_stage("decode", cases)


def pre_case(name, text, merges):
    return case(
        name,
        ["encode", "text.txt", "--merges", "merges.json", "--pretokenize", "gpt2"],
        merges_file(merges, **text_file("text.txt", text)),
        reference.encode_text(text, merges, pretokenize=True),
        gpt2_chunks(text),
    )


def stage_pretokenize():
    cases = [pre_case("visible", "Hello world's 123!!", [[108, 108], [111, 32]])]
    samples = [
        ("uppercase-stays-split", "DON'T"),
        ("hindi-combining-marks", "हिंदी"),
        ("non-breaking-space", "foo\u00a0bar"),
    ]
    for name, text in samples:
        # Train without the regex so some merges sit on chunk boundaries.
        cases.append(pre_case(name, text, reference.train(text, 8)))
    # 't is a contraction. 'T is not, so DON'T keeps 39, 84.
    cases.append(pre_case("contraction-case", "don't DON'T", [[39, 116], [39, 84]]))
    # Each non-breaking space is its own chunk. Two of them do not become one
    # token, and the second one does not stick to "bar".
    nbsp = "foo\u00a0\u00a0bar"
    cases.append(pre_case("two-non-breaking-spaces", nbsp, [[194, 160], [256, 256], [256, 98]]))
    write_stage("pretokenize", cases)


def stage_gpt2():
    enc = tiktoken.get_encoding("gpt2")
    samples = [
        ("visible-hello-world", "Hello world"),
        ("strawberry-leading-space", "strawberry strawberry"),
        ("hindi-sentence", "नमस्ते दुनिया"),
        ("code", "fn main() {\n    return;\n}\n"),
        # ## is a real merge that starts with #. The blank line stays two newlines.
        ("markdown-heading", "## Title\n\nSome text"),
    ]
    cases = []
    for name, text in samples:
        expected = enc.encode(text)
        got = reference.encode_gpt2(text, str(GPT2_DIR))
        if got != expected:
            raise SystemExit(f"{name!r} reference {got} != tiktoken {expected}")
        cases.append(
            case(
                name,
                ["encode", "text.txt", "--vocab", "gpt2"],
                text_file("text.txt", text),
                expected,
            )
        )
    write_stage("gpt2-match", cases)


def main():
    if not (GPT2_DIR / "vocab.json").exists() or not (GPT2_DIR / "merges.txt").exists():
        raise SystemExit(f"missing GPT-2 files in {GPT2_DIR}")
    stage_bytes()
    stage_top_pair()
    stage_merge()
    stage_train()
    stage_encode()
    stage_decode()
    stage_pretokenize()
    stage_gpt2()


if __name__ == "__main__":
    main()
