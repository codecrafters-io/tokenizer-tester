package internal

import "github.com/codecrafters-io/tester-utils/test_case_harness"

func testTopPair(harness *test_case_harness.TestCaseHarness) error {
	return runFixture(harness, "top-pair")
}
