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
