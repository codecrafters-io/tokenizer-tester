package internal

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestPassAll(t *testing.T) {
	repo, err := filepath.Abs("test_helpers/pass_all")
	if err != nil {
		t.Fatal(err)
	}

	type testCase struct {
		Slug            string `json:"slug"`
		TesterLogPrefix string `json:"tester_log_prefix"`
		Title           string `json:"title"`
	}
	cases := make([]testCase, len(testerDefinition.TestCases))
	for i, stage := range testerDefinition.TestCases {
		cases[i] = testCase{
			Slug:            stage.Slug,
			TesterLogPrefix: "stage-" + itoa(i+1),
			Title:           "Stage #" + itoa(i+1),
		}
	}
	encoded, err := json.Marshal(cases)
	if err != nil {
		t.Fatal(err)
	}

	code := RunCLI(map[string]string{
		"CODECRAFTERS_REPOSITORY_DIR":  repo,
		"CODECRAFTERS_TEST_CASES_JSON": string(encoded),
	})
	if code != 0 {
		t.Fatalf("reference solution failed, tester exit code %d", code)
	}
}

// A program that breaks ties by hash map order can pass a tie case once by
// luck. The flaky_ties program is right on the first run of each input and
// wrong after that, so only running a tie case again catches it.
func TestTieCasesRunMoreThanOnce(t *testing.T) {
	repo, err := filepath.Abs("test_helpers/flaky_ties")
	if err != nil {
		t.Fatal(err)
	}
	state := t.TempDir()
	t.Setenv("TOKENIZER_FLAKY_STATE_DIR", state)

	code := RunCLI(map[string]string{
		"CODECRAFTERS_REPOSITORY_DIR":  repo,
		"CODECRAFTERS_TEST_CASES_JSON": `[{"slug":"gk8","tester_log_prefix":"stage-2","title":"Stage #2"}]`,
	})
	if code == 0 {
		t.Fatal("tester passed a program whose tie answers change between runs")
	}

	// The failure must come from a second run of the first tie case, not
	// from something earlier going wrong.
	runs, err := os.ReadFile(filepath.Join(state, sha256Hex("[8, 9, 1, 2]")))
	if err != nil {
		t.Fatalf("tie-first-pair-wins never ran: %v", err)
	}
	if string(runs) != "2" {
		t.Fatalf("tie-first-pair-wins ran %s times, want 2", runs)
	}
}

func sha256Hex(text string) string {
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	digits := []byte{}
	for n > 0 {
		digits = append([]byte{byte('0' + n%10)}, digits...)
		n /= 10
	}
	return string(digits)
}
