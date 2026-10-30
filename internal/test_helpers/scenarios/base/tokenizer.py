#!/usr/bin/env python3
"""Reference byte-level BPE tokenizer for the tokenizer tester.

Stages 1-7 use byte values as token ids. Merge i creates token 256 + i.
Stage 8 loads GPT-2 vocab.json and merges.txt.
"""

import json
import sys

import regex

# tiktoken's gpt2 / r50k pretokenizer. The last alternative is a single
# whitespace character, matching tiktoken_ext.openai_public.r50k_pat_str.
GPT2_PAT = regex.compile(
    r"""'(?:[sdmt]|ll|ve|re)| ?\p{L}++| ?\p{N}++| ?[^\s\p{L}\p{N}]++|\s++$|\s+(?!\S)|\s"""
)


def get_stats(ids):
    counts = {}
    for pair in zip(ids, ids[1:]):
        counts[pair] = counts.get(pair, 0) + 1
    return counts


def merge(ids, pair, idx):
    new_ids = []
    i = 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
            new_ids.append(idx)
            i += 2
        else:
            new_ids.append(ids[i])
            i += 1
    return new_ids


def top_pair(ids):
    stats = get_stats(ids)
    if not stats:
        raise SystemExit("top-pair needs at least two ids")
    pair = max(stats, key=stats.get)
    return [pair[0], pair[1]]


def train(text, num_merges):
    ids = list(text.encode("utf-8"))
    merges = []
    for i in range(num_merges):
        stats = get_stats(ids)
        if not stats:
            break
        pair = max(stats, key=stats.get)
        ids = merge(ids, pair, 256 + i)
        merges.append([pair[0], pair[1]])
    return merges


def merge_ranks(merges):
    return {(pair[0], pair[1]): 256 + i for i, pair in enumerate(merges)}


def encode_ids(ids, merges):
    ranks = merge_ranks(merges)
    while len(ids) >= 2:
        stats = get_stats(ids)
        pair = min(stats, key=lambda item: ranks.get(item, float("inf")))
        if pair not in ranks:
            break
        ids = merge(ids, pair, ranks[pair])
    return ids


def encode_text(text, merges, pretokenize=False):
    if not pretokenize:
        return encode_ids(list(text.encode("utf-8")), merges)
    ids = []
    for chunk in GPT2_PAT.findall(text):
        ids.extend(encode_ids(list(chunk.encode("utf-8")), merges))
    return ids


def vocab_bytes(merges):
    vocab = {idx: bytes([idx]) for idx in range(256)}
    for i, pair in enumerate(merges):
        vocab[256 + i] = vocab[pair[0]] + vocab[pair[1]]
    return vocab


def decode_ids(ids, merges):
    vocab = vocab_bytes(merges)
    data = b"".join(vocab[idx] for idx in ids)
    return data.decode("utf-8", errors="replace")


def bytes_to_unicode():
    printable = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    byte_values = list(printable)
    codepoints = list(printable)
    extra = 0
    for value in range(256):
        if value not in printable:
            byte_values.append(value)
            codepoints.append(256 + extra)
            extra += 1
    return {value: chr(point) for value, point in zip(byte_values, codepoints)}


def load_merges_txt(path):
    """Skip blank lines and only a leading `#version` line.

    Later lines that start with `#` are real merges, such as `# #`.
    """
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    start = 1 if lines and lines[0].startswith("#version") else 0
    pairs = []
    for line in lines[start:]:
        if line == "":
            continue
        left, right = line.split(" ", 1)
        pairs.append((left, right))
    return pairs


def bpe_word(word, ranks):
    """GPT-2's character-space merge loop. `word` is a tuple of strings."""
    if len(word) < 2:
        return word
    while True:
        pairs = set(zip(word, word[1:]))
        bigram = min(pairs, key=lambda pair: ranks.get(pair, float("inf")))
        if bigram not in ranks:
            break
        first, second = bigram
        merged = []
        i = 0
        while i < len(word):
            try:
                j = word.index(first, i)
            except ValueError:
                merged.extend(word[i:])
                break
            merged.extend(word[i:j])
            i = j
            if i < len(word) - 1 and word[i] == first and word[i + 1] == second:
                merged.append(first + second)
                i += 2
            else:
                merged.append(word[i])
                i += 1
        word = tuple(merged)
        if len(word) == 1:
            break
    return word


def encode_gpt2(text, vocab_dir):
    with open(f"{vocab_dir}/vocab.json", encoding="utf-8") as handle:
        vocab = json.load(handle)
    ranks = {pair: index for index, pair in enumerate(load_merges_txt(f"{vocab_dir}/merges.txt"))}
    mapping = bytes_to_unicode()
    ids = []
    for chunk in GPT2_PAT.findall(text):
        symbols = tuple(mapping[byte] for byte in chunk.encode("utf-8"))
        for piece in bpe_word(symbols, ranks):
            ids.append(vocab[piece])
    return ids


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def emit(value):
    json.dump(value, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")


def flag(args, name):
    if name not in args:
        raise SystemExit(f"missing {name}")
    index = args.index(name)
    return args[index + 1]


def main(argv):
    if len(argv) < 2:
        raise SystemExit("usage: tokenizer.py <command> [args]")
    command = argv[1]
    args = argv[2:]

    if command == "bytes":
        with open(args[0], "rb") as handle:
            emit(list(handle.read()))
        return
    if command == "top-pair":
        emit(top_pair(read_json(args[0])))
        return
    if command == "merge":
        ids = read_json(args[0])
        left, right = (int(part) for part in flag(args, "--pair").split(","))
        emit(merge(ids, (left, right), 256))
        return
    if command == "train":
        with open(args[0], encoding="utf-8") as handle:
            text = handle.read()
        emit(train(text, int(flag(args, "--merges"))))
        return
    if command == "encode":
        with open(args[0], encoding="utf-8") as handle:
            text = handle.read()
        if "--vocab" in args:
            emit(encode_gpt2(text, flag(args, "--vocab")))
            return
        merges = read_json(flag(args, "--merges"))
        pretokenize = "--pretokenize" in args and flag(args, "--pretokenize") == "gpt2"
        emit(encode_text(text, merges, pretokenize))
        return
    if command == "decode":
        ids = read_json(args[0])
        merges = read_json(flag(args, "--merges"))
        emit(decode_ids(ids, merges))
        return
    raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    main(sys.argv)
