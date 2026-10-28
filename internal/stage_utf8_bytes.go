package internal

import "github.com/codecrafters-io/tester-utils/test_case_harness"

func testUTF8Bytes(harness *test_case_harness.TestCaseHarness) error {
	return runFixture(harness, "utf8-bytes")
}
