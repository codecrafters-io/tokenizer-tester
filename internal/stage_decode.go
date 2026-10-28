package internal

import "github.com/codecrafters-io/tester-utils/test_case_harness"

func testDecode(harness *test_case_harness.TestCaseHarness) error {
	return runFixture(harness, "decode")
}
