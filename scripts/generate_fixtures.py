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


def case(name, args, files, expected):
    return {"name": name, "args": args, "files": files, "expected": expected}


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
        ("visible-wave", f"hi {WAVE}"),
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
        ("visible-aaabdaaabac", corpus),
        ("tie-not-lowest-id", [8, 9, 1, 2]),
        ("aaa-counts-twice", [97, 97, 97]),
        ("single-pair", [4, 5]),
    ]
    cases = []
    for name, ids in sequences:
        cases.append(case(name, ["top-pair", "ids.json"], ids_file(ids), reference.top_pair(ids)))
    write_stage("top-pair", cases)


def stage_merge():
    corpus = list("aaabdaaabac".encode())
    specs = [
        ("visible", corpus, 97, 97),
        ("aaa", [97, 97, 97], 97, 97),
        ("missing-pair", [1, 2, 3], 9, 9),
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
    }
    cases = []
    for name, (text, count) in texts.items():
        expected = reference.train(text, count)
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
    write_stage("encode", cases)


def stage_decode():
    merges = reference.train("aaabdaaabac", 3)
    specs = [
        ("visible", [258, 100], merges),
        ("half-wave", [240, 159], []),
        ("full-wave", [240, 159, 145, 139], []),
        ("two-invalid", [255, 255], []),
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


def stage_pretokenize():
    visible_merges = [[108, 108], [111, 32]]
    visible_text = "Hello world's 123!!"
    cases = [
        case(
            "visible",
            ["encode", "text.txt", "--merges", "merges.json", "--pretokenize", "gpt2"],
            merges_file(visible_merges, **text_file("text.txt", visible_text)),
            reference.encode_text(visible_text, visible_merges, pretokenize=True),
        )
    ]
    samples = [
        "DON'T",
        "हिंदी",
        "foo\u00a0bar",
    ]
    for index, text in enumerate(samples):
        # Train without the regex so some merges sit on chunk boundaries.
        merges = reference.train(text if text else "hello", 8)
        cases.append(
            case(
                f"hidden-{index}",
                ["encode", "text.txt", "--merges", "merges.json", "--pretokenize", "gpt2"],
                merges_file(merges, **text_file("text.txt", text)),
                reference.encode_text(text, merges, pretokenize=True),
            )
        )
    write_stage("pretokenize", cases)


def stage_gpt2():
    enc = tiktoken.get_encoding("gpt2")
    samples = [
        ("visible-hello-world", "Hello world"),
        ("visible-leading-space", " Hello world"),
        ("hindi-sentence", "नमस्ते दुनिया"),
        ("code", "fn main() {\n    return;\n}\n"),
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
