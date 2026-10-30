package internal

import (
	"time"

	"github.com/codecrafters-io/tester-utils/tester_definition"
)

var testerDefinition = tester_definition.TesterDefinition{
	AntiCheatTestCases: []tester_definition.TestCase{},
	ExecutableFileName: "your_program.sh",
	TestCases: []tester_definition.TestCase{
		{Slug: "kx8", TestFunc: testUTF8Bytes},
		{Slug: "gk8", TestFunc: testTopPair},
		{Slug: "fk3", TestFunc: testApplyMerge},
		{Slug: "ur9", TestFunc: testTrainBPE},
		{Slug: "kz6", TestFunc: testEncode},
		{Slug: "vg5", TestFunc: testDecode},
		// runFixture caps each execution at 15s. The stage cap covers every run.
		{Slug: "wl7", TestFunc: testPretokenize, Timeout: 6*15*time.Second + 30*time.Second},
		{Slug: "as1", TestFunc: testGPT2Match, Timeout: 5*15*time.Second + 30*time.Second},
	},
}
