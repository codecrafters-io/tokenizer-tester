package internal

import "github.com/codecrafters-io/tester-utils/test_case_harness"

func testGPT2Match(harness *test_case_harness.TestCaseHarness) error {
	return runFixture(harness, "gpt2-match")
}
