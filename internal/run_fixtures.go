package internal

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strconv"
	"strings"

	"github.com/codecrafters-io/tester-utils/test_case_harness"
	"github.com/codecrafters-io/tokenizer-tester/internal/fixtures"
)

type fixtureCase struct {
	Name     string            `json:"name"`
	Args     []string          `json:"args"`
	Files    map[string]string `json:"files"`
	Expected json.RawMessage   `json:"expected"`
}

func runFixture(harness *test_case_harness.TestCaseHarness, slug string) error {
	raw, err := fixtures.FS.ReadFile(slug + ".json")
	if err != nil {
		return fmt.Errorf("read fixtures for %s: %w", slug, err)
	}

	var cases []fixtureCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		return fmt.Errorf("parse fixtures for %s: %w", slug, err)
	}

	logger := harness.Logger
	for _, testCase := range cases {
		workDir, err := os.MkdirTemp("", "tokenizer-"+slug+"-")
		if err != nil {
			return err
		}
		defer os.RemoveAll(workDir)

		names := make([]string, 0, len(testCase.Files))
		for name := range testCase.Files {
			names = append(names, name)
		}
		sort.Strings(names)
		sort.SliceStable(names, func(i, j int) bool {
			return argPosition(testCase.Args, names[i]) < argPosition(testCase.Args, names[j])
		})

		for _, name := range names {
			contents := testCase.Files[name]
			path := filepath.Join(workDir, name)
			if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
				return err
			}
			if err := os.WriteFile(path, []byte(contents), 0o644); err != nil {
				return err
			}
			logger.Infof("Wrote %s: %s", name, describeFile(name, contents))
		}

		if contains(testCase.Args, "--vocab") {
			if err := materializeGPT2(workDir); err != nil {
				return err
			}
			logger.Infof("Wrote GPT-2's vocabulary to gpt2/vocab.json and gpt2/merges.txt")
		}

		logger.Infof("$ ./%s %s", filepath.Base(harness.Executable.Path), strings.Join(testCase.Args, " "))

		executable := harness.NewExecutable()
		executable.WorkingDir = workDir
		executable.TimeoutInMilliseconds = 15 * 1000
		result, err := executable.Run(testCase.Args...)
		if err != nil {
			return fmt.Errorf("%s: %w", testCase.Name, err)
		}

		actual, err := parseJSONValue(result.Stdout)
		if err != nil {
			return fmt.Errorf("%s: %w\nstdout: %q", testCase.Name, err, result.Stdout)
		}
		expected, err := parseJSONValue(testCase.Expected)
		if err != nil {
			return fmt.Errorf("%s: fixture: %w", testCase.Name, err)
		}
		if !reflect.DeepEqual(actual, expected) {
			return fmt.Errorf("%s: expected %s, got %s", testCase.Name, preview(expected), preview(actual))
		}
		logger.Successf("%s passed", testCase.Name)
	}

	return nil
}

func materializeGPT2(workDir string) error {
	return fs.WalkDir(fixtures.FS, "gpt2", func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		target := filepath.Join(workDir, filepath.FromSlash(path))
		if entry.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		data, err := fixtures.FS.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, data, 0o644)
	})
}

func parseJSONValue(raw []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(bytes.TrimSpace(raw)))
	dec.UseNumber()
	var value any
	if err := dec.Decode(&value); err != nil {
		return nil, fmt.Errorf("stdout is not one JSON value: %w", err)
	}
	var trailing any
	err := dec.Decode(&trailing)
	if err == nil {
		return nil, fmt.Errorf("stdout has extra data after the JSON value")
	}
	if !errors.Is(err, io.EOF) {
		return nil, fmt.Errorf("stdout has extra data after the JSON value: %w", err)
	}
	return normalize(value), nil
}

func normalize(value any) any {
	switch typed := value.(type) {
	case json.Number:
		return typed
	case []any:
		for i, item := range typed {
			typed[i] = normalize(item)
		}
		return typed
	default:
		return value
	}
}

func preview(value any) string {
	encoded, err := json.Marshal(value)
	if err != nil {
		return fmt.Sprint(value)
	}
	text := string(encoded)
	if len(text) > 240 {
		return text[:240] + "..."
	}
	return text
}

// JSON files are shown as written. Text files are quoted so newlines and
// empty files stay visible.
func describeFile(name string, contents string) string {
	const limit = 200
	runes := []rune(contents)
	truncated := len(runes) > limit
	if truncated {
		runes = runes[:limit]
	}

	shown := string(runes)
	if !strings.HasSuffix(name, ".json") {
		shown = strconv.Quote(shown)
	}
	if truncated {
		shown += fmt.Sprintf(" ... (%d bytes total)", len(contents))
	}
	return shown
}

func argPosition(args []string, name string) int {
	for i, arg := range args {
		if arg == name {
			return i
		}
	}
	return len(args)
}

func contains(args []string, needle string) bool {
	for _, arg := range args {
		if arg == needle {
			return true
		}
	}
	return false
}
