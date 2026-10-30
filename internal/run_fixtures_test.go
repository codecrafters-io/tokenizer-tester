package internal

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestEmptyStdoutIsNotAnEOFError(t *testing.T) {
	_, err := parseJSONValue(nil)
	if err == nil || strings.Contains(err.Error(), "EOF") {
		t.Fatalf("empty stdout: %v", err)
	}
	if !strings.Contains(err.Error(), "printed nothing") {
		t.Fatalf("empty stdout: %v", err)
	}
}

func TestExtraStdoutLines(t *testing.T) {
	_, err := parseJSONValue([]byte("[1, 2]\ndebug line\n"))
	if err == nil || !strings.Contains(err.Error(), "got 2 lines") {
		t.Fatalf("extra lines: %v", err)
	}
	if !strings.Contains(err.Error(), "stderr") {
		t.Fatalf("extra lines: %v", err)
	}
}

func TestFirstDifference(t *testing.T) {
	expected, err := parseJSONValue([]byte("[[97,97],[256,97],[257,98]]"))
	if err != nil {
		t.Fatal(err)
	}
	actual, err := parseJSONValue([]byte("[[97,97],[256,98],[257,98]]"))
	if err != nil {
		t.Fatal(err)
	}
	message := mismatch(expected, actual)
	if !strings.Contains(message, "index 1") || !strings.Contains(message, "[256,97]") || !strings.Contains(message, "[256,98]") {
		t.Fatalf("mismatch: %s", message)
	}
}

func TestStringMismatchIsEscaped(t *testing.T) {
	message := mismatch("a\u009fb", "a\uFFFDb")
	if strings.Contains(message, "\u009f") || strings.Contains(message, "\uFFFD") {
		t.Fatalf("raw characters leaked: %s", message)
	}
	if !strings.Contains(message, `\u009f`) || !strings.Contains(message, `\ufffd`) {
		t.Fatalf("escapes missing: %s", message)
	}
}

func TestByteHint(t *testing.T) {
	actual, err := parseJSONValue([]byte("[104, 256]"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(hint("utf8-bytes", fixtureCase{}, actual), "255") {
		t.Fatalf("hint: %s", hint("utf8-bytes", fixtureCase{}, actual))
	}
}

func TestUnmergedHint(t *testing.T) {
	raw := "[1, 2, 3]"
	actual, err := parseJSONValue([]byte(raw))
	if err != nil {
		t.Fatal(err)
	}
	testCase := fixtureCase{Files: map[string]string{"ids.json": raw}}
	if !strings.Contains(hint("apply-merge", testCase, actual), "nothing got merged") {
		t.Fatal(hint("apply-merge", testCase, actual))
	}
}

func TestNullVocabHint(t *testing.T) {
	actual, err := parseJSONValue([]byte("[15496, null]"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(hint("gpt2-match", fixtureCase{}, actual), "vocab.json") {
		t.Fatal(hint("gpt2-match", fixtureCase{}, actual))
	}
}

func TestChunksSuffix(t *testing.T) {
	suffix := chunksSuffix(fixtureCase{Chunks: []string{"DON", "'", "T"}})
	if suffix != `. Chunks: "DON" "'" "T"` {
		t.Fatalf("chunks: %s", suffix)
	}
}

func TestJSONNumberStaysANumber(t *testing.T) {
	value, err := parseJSONValue([]byte("[104, 105]"))
	if err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if string(encoded) != "[104,105]" {
		t.Fatalf("encoded %s", encoded)
	}
}
