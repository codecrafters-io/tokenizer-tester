#!/usr/bin/env python3
"""Freeze expected stdout for every tokenizer stage.

Run from the tester repo with a Python that has `regex` and `tiktoken`:

    python3 scripts/generate_fixtures.py
"""

import json
import random
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
        ("devanagari-na", "न"),
        ("empty", ""),
        ("hello", "hello"),
        ("newline", "a\nb"),
        ("tab", "a\tb"),
        ("emoji-only", "🙂"),
        ("hindi-word", "हिंदी"),
        ("tamil-word", "தமிழ்"),
        ("mixed", "aनb"),
        ("spaces", "  x"),
        ("nbsp", "foo\u00a0bar"),
        ("code", "fn main() {}"),
        ("punctuation", "Hello, world!"),
        ("digits", "12345"),
        ("quotes", "it's"),
        ("caps", "DON'T"),
        ("null-char", "a\u0000b"),
        ("cjk", "你好"),
        ("skin-tone", "👋🏻"),
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
        ("all-same", [7, 7, 7, 7]),
        ("unique-pairs", [1, 2, 3, 4, 5]),
    ]
    rng = random.Random(8)
    while len(sequences) < 21:
        length = rng.randint(2, 24)
        sequences.append((f"random-{len(sequences)}", [rng.randint(0, 40) for _ in range(length)]))
    cases = []
    for name, ids in sequences:
        cases.append(case(name, ["top-pair", "ids.json"], ids_file(ids), reference.top_pair(ids)))
    write_stage("top-pair", cases)


def stage_merge():
    corpus = list("aaabdaaabac".encode())
    specs = [
        ("visible", corpus, 97, 97, 256),
        ("aaa", [97, 97, 97], 97, 97, 256),
        ("aaaa", [97, 97, 97, 97], 97, 97, 256),
        ("missing-pair", [1, 2, 3], 9, 9, 256),
        ("pair-at-end", [1, 2, 3, 3], 3, 3, 300),
        ("no-overlap-abab", [97, 98, 97, 98], 97, 98, 256),
    ]
    rng = random.Random(3)
    while len(specs) < 21:
        ids = [rng.randint(0, 12) for _ in range(rng.randint(2, 16))]
        left, right = rng.choice(ids), rng.choice(ids)
        specs.append((f"random-{len(specs)}", ids, left, right, 256 + len(specs)))
    cases = []
    for name, ids, left, right, new_id in specs:
        cases.append(
            case(
                name,
                ["merge", "ids.json", "--pair", f"{left},{right}", "--new", str(new_id)],
                ids_file(ids),
                reference.merge(ids, (left, right), new_id),
            )
        )
    write_stage("apply-merge", cases)


def stage_train():
    texts = {
        "visible": ("aaabdaaabac", 3),
        "one-merge": ("aaabdaaabac", 1),
        "six-merges": ("aaabdaaabac", 6),
        "hello-repeated": ("hello hello hello\n" * 4, 10),
    }
    paragraph = (
        "Byte pair encoding merges the most common pair. "
        "It keeps doing that until the vocabulary is large enough for the corpus.\n"
    )
    texts["fifty-merges"] = (paragraph * 3, 50)
    texts["short-words"] = ("cat sat mat cat sat\n" * 5, 20)
    extra = [
        "नमस्ते दुनिया ",
        "fn add(a: i32) -> i32 { a }\n",
        "wave " + WAVE + " wave " + WAVE + "\n",
        "don't won't can't it's\n",
    ]
    for index, text in enumerate(extra):
        texts[f"extra-{index}"] = (text * 4, 15)
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
        ("single-a", "a"),
        ("aaa", "aaa"),
        ("unrelated", "hello"),
        ("aa", "aa"),
        ("aaab-twice", "aaabXaaab"),
    ]
    rng = random.Random(5)
    alphabet = "aaabdX"
    while len(samples) < 21:
        samples.append((f"random-{len(samples)}", "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))))
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
        ("round-trip", reference.encode_text("aaabdaaabac", merges), merges),
        ("single-byte", [104], []),
        ("invalid-byte", [255], []),
        ("two-invalid", [255, 255], []),
        ("emoji-split-kept", [240, 159, 145, 139], []),
        ("empty", [], []),
        ("training-tokens", [258, 100, 258, 97, 99], merges),
    ]
    for extra in range(10):
        specs.append((f"mixed-{extra}", [extra, 240, 159, extra + 1], []))
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
        "Hello, world's 123",
        "a   b",
        "  hello",
        "it's a test",
        "end  ",
        "\n\n",
        "I'm",
        "12345",
        "a\tb",
        "Hello, world!!!? (안녕하세요!) lol123",
        "தமிழ்",
        "fn main() {\n    return;\n}\n",
        WAVE,
        "hi " + WAVE,
        "dog. dog! dog?",
        "   ",
        "don't DON'T",
        "price is $12.50 today",
        "café",
        "line one\nline two",
        "!!??",
        "  42",
        "world's",
        "A\u0301",  # A + combining acute, category M on the second char
        "hello  world",
        "",
        "spaces\u00a0and more",
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
        ("empty", ""),
        ("bang", "!"),
        ("letter-a", "a"),
        ("space", " "),
        ("newline", "\n"),
        ("dont", "don't"),
        ("dont-caps", "DON'T"),
        ("hindi", "हिंदी"),
        ("hindi-sentence", "नमस्ते दुनिया"),
        ("tamil", "தமிழ்"),
        ("tamil-sentence", "வணக்கம் உலகம்"),
        ("emoji", WAVE),
        ("hi-emoji", f"hi {WAVE}"),
        ("smile", "🙂"),
        ("code", "fn main() {\n    return;\n}\n"),
        ("python", "def add(a, b):\n    return a + b\n"),
        ("nbsp", "foo\u00a0bar"),
        ("repeated-spaces", "hello  world"),
        ("leading-spaces", "  hello"),
        ("trailing-spaces", "end  "),
        ("newlines", "\n\n"),
        ("tabs", "a\tb"),
        ("punctuation", "Hello, world's 123!!"),
        ("cjk", "你好世界"),
        ("korean", "안녕하세요"),
        ("digits", "12345"),
        ("money", "price is $12.50 today"),
        ("contraction", "it's a test"),
        ("im", "I'm"),
        ("question", "Hello, world!!!? (안녕하세요!) lol123"),
        ("dog", "dog. dog! dog?"),
        ("only-spaces", "   "),
        ("combining", "A\u0301"),
        ("devanagari-letter", "न"),
        ("quote", '"hello"'),
        ("slash", "a/b/c"),
        ("urlish", "https://example.com/a"),
        ("mixed-emoji", "ok 👍🏻"),
        ("indent", "\tif x:\n\t\treturn\n"),
        ("blank-line", "one\n\ntwo"),
        ("comma", "red, green, blue"),
        ("apostrophe-word", "world's"),
        ("caps-hello", "HELLO"),
        ("lower-hello", "hello"),
        ("number-word", "room 101"),
        ("ellipsis", "wait..."),
        ("parens", "(yes)"),
        ("skin-and-zwj", "👨‍💻"),
        ("equals", "a == b"),
        ("hindi-code", "मान = 1"),
    ]
    if len(samples) != 52:
        raise SystemExit(f"stage 8 has {len(samples)} texts, want 52")
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
