package internal

import (
	"encoding/json"
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
