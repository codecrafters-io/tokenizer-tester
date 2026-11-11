package internal

import (
	"reflect"
	"strings"
	"testing"
)

// The expected pieces come from tiktoken's gpt2 encoding
// (decode_single_token_bytes), not from this package.
func TestGPT2PiecesMatchTiktoken(t *testing.T) {
	cases := []struct {
		ids  string
		want []string
	}{
		{"[301, 1831, 8396]", []string{`"st"`, `"raw"`, `"berry"`}},
		{"[301, 1831, 8396, 41236]", []string{`"st"`, `"raw"`, `"berry"`, `" strawberry"`}},
		{"[15496, 995]", []string{`"Hello"`, `" world"`}},
		{"[15496, 198, 198, 6894]", []string{`"Hello"`, `"\n"`, `"\n"`, `"world"`}},
		// The wave emoji is split across two tokens, so neither is valid UTF-8.
		{"[41840, 233]", []string{`"\xf0\x9f\x91"`, `"\x8b"`}},
	}
	for _, testCase := range cases {
		ids, err := parseJSONValue([]byte(testCase.ids))
		if err != nil {
			t.Fatal(err)
		}
		got, ok := gpt2Pieces(ids)
		if !ok || !reflect.DeepEqual(got, testCase.want) {
			t.Errorf("%s: got %v (ok=%v), want %v", testCase.ids, got, ok, testCase.want)
		}
	}
}

func TestGPT2PiecesLeavesOutWhatItCannotShow(t *testing.T) {
	long := "[" + strings.Repeat("262, ", maxPiecesShown) + "262]"
	for _, raw := range []string{`[]`, `[50300]`, `[-1]`, `["st"]`, `"st"`, `[1.5]`, long} {
		value, err := parseJSONValue([]byte(raw))
		if err != nil {
			t.Fatal(err)
		}
		if pieces, ok := gpt2Pieces(value); ok {
			t.Errorf("%s: expected no pieces, got %v", raw, pieces)
		}
	}
}

func TestPiecesSuffixShowsBothSides(t *testing.T) {
	expected, _ := parseJSONValue([]byte("[301, 1831, 8396]"))
	actual, _ := parseJSONValue([]byte("[2536, 707, 8396]"))
	suffix := piecesSuffix(expected, actual)
	if !strings.Contains(suffix, `Expected pieces: "st" "raw" "berry"`) || !strings.Contains(suffix, `Your pieces:     "str" "aw" "berry"`) {
		t.Fatalf("suffix: %s", suffix)
	}
}

// The ids are GPT-2's single-byte tokens as tiktoken reports them: a is 64,
// ! is 0, a space is 220, and a newline is 198.
func TestGPT2OneIDPerByte(t *testing.T) {
	got, ok := gpt2OneIDPerByte("a! \n")
	want, _ := parseJSONValue([]byte("[64, 0, 220, 198]"))
	if !ok || !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v (ok=%v), want %v", got, ok, want)
	}
}

func TestGPT2MatchHintsTellFailuresApart(t *testing.T) {
	testCase := fixtureCase{Files: map[string]string{"text.txt": "a! \n"}}
	cases := []struct {
		actual string
		want   string
	}{
		{"[97, 33, 32, 10]", "byte values"},
		{"[64, 0, 220, 198]", "one id per byte"},
		{"[64, null]", "null id"},
		{"[64, 0, 220]", ""},
	}
	for _, c := range cases {
		actual, err := parseJSONValue([]byte(c.actual))
		if err != nil {
			t.Fatal(err)
		}
		got := hint("gpt2-match", testCase, actual)
		if (c.want == "" && got != "") || !strings.Contains(got, c.want) {
			t.Errorf("%s: hint %q, want it to contain %q", c.actual, got, c.want)
		}
	}
}
