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
	Chunks   []string          `json:"chunks,omitempty"`
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
			message := err.Error()
			if slug == "encode" && strings.Contains(message, "timed out") {
				message += ". A timeout usually means the loop never stops"
			}
			return fmt.Errorf("%s: %s%s", testCase.Name, message, chunksSuffix(testCase))
		}
		if result.ExitCode != 0 && len(bytes.TrimSpace(result.Stdout)) == 0 {
			return fmt.Errorf("%s: your program exited with code %d and printed nothing to stdout%s", testCase.Name, result.ExitCode, chunksSuffix(testCase))
		}

		actual, err := parseJSONValue(result.Stdout)
		if err != nil {
			return fmt.Errorf("%s: %w%s", testCase.Name, err, chunksSuffix(testCase))
		}
		expected, err := parseJSONValue(testCase.Expected)
		if err != nil {
			return fmt.Errorf("%s: fixture: %w", testCase.Name, err)
		}
		if !reflect.DeepEqual(actual, expected) {
			return fmt.Errorf("%s: %s%s%s", testCase.Name, mismatch(expected, actual), hint(slug, testCase, actual), chunksSuffix(testCase))
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
	if len(bytes.TrimSpace(raw)) == 0 {
		return nil, fmt.Errorf("expected a JSON value on stdout, like [104, 105], but your program printed nothing")
	}
	dec := json.NewDecoder(bytes.NewReader(bytes.TrimSpace(raw)))
	dec.UseNumber()
	var value any
	if err := dec.Decode(&value); err != nil {
		if errors.Is(err, io.EOF) {
			return nil, fmt.Errorf("expected a JSON value on stdout, like [104, 105], but your program printed nothing")
		}
		return nil, fmt.Errorf("expected a JSON value on stdout, like [104, 105]: %w", err)
	}
	var trailing any
	err := dec.Decode(&trailing)
	if err == nil || !errors.Is(err, io.EOF) {
		lines := lineCount(raw)
		if lines > 1 {
			return nil, fmt.Errorf("expected one JSON value on stdout, got %d lines. Send debug output to stderr", lines)
		}
		return nil, fmt.Errorf("expected one JSON value on stdout, got extra data after it. Send debug output to stderr")
	}
	return normalize(value), nil
}

func lineCount(raw []byte) int {
	if len(raw) == 0 {
		return 0
	}
	count := bytes.Count(raw, []byte("\n"))
	if raw[len(raw)-1] != '\n' {
		count++
	}
	return count
}

func mismatch(expected, actual any) string {
	if message, ok := firstDifference(expected, actual); ok {
		return message
	}
	return fmt.Sprintf("expected %s, got %s", preview(expected), preview(actual))
}

func firstDifference(expected, actual any) (string, bool) {
	exp, expOK := expected.([]any)
	act, actOK := actual.([]any)
	if expOK && actOK {
		limit := len(exp)
		if len(act) < limit {
			limit = len(act)
		}
		for i := 0; i < limit; i++ {
			if reflect.DeepEqual(exp[i], act[i]) {
				continue
			}
			return fmt.Sprintf("first difference at index %d: expected %s, got %s", i, preview(exp[i]), preview(act[i])), true
		}
		if len(exp) != len(act) {
			return fmt.Sprintf("first difference at index %d: expected %d values, got %d", limit, len(exp), len(act)), true
		}
	}
	if expText, ok := expected.(string); ok {
		actText, ok := actual.(string)
		if !ok {
			return "", false
		}
		return fmt.Sprintf("expected %s, got %s", fmt.Sprintf("%+q", expText), fmt.Sprintf("%+q", actText)), true
	}
	return "", false
}

func hint(slug string, testCase fixtureCase, actual any) string {
	switch slug {
	case "utf8-bytes":
		if numberAbove255(actual) {
			return ". Numbers above 255 mean you printed characters, not bytes"
		}
	case "apply-merge":
		if sameJSON(testCase.Files["ids.json"], actual) {
			return ". The output matches the input, so nothing got merged"
		}
	case "encode":
		if sameUTF8Bytes(testCase.Files["text.txt"], actual) {
			return ". The output matches the input bytes, so nothing got merged"
		}
	case "gpt2-match":
		if containsNull(actual) {
			return ". A null id means a piece isn't in vocab.json, which usually means the byte-to-character table is off"
		}
	}
	return ""
}

func numberAbove255(value any) bool {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			if numberAbove255(item) {
				return true
			}
		}
	case json.Number:
		number, err := typed.Int64()
		return err == nil && number > 255
	}
	return false
}

func containsNull(value any) bool {
	switch typed := value.(type) {
	case nil:
		return true
	case []any:
		for _, item := range typed {
			if containsNull(item) {
				return true
			}
		}
	}
	return false
}

func sameJSON(raw string, actual any) bool {
	if raw == "" {
		return false
	}
	parsed, err := parseJSONValue([]byte(raw))
	if err != nil {
		return false
	}
	return reflect.DeepEqual(parsed, actual)
}

func sameUTF8Bytes(text string, actual any) bool {
	if _, ok := actual.([]any); !ok && text == "" {
		return false
	}
	numbers := make([]any, len(text))
	for i, value := range []byte(text) {
		numbers[i] = json.Number(strconv.Itoa(int(value)))
	}
	return reflect.DeepEqual(numbers, actual)
}

func chunksSuffix(testCase fixtureCase) string {
	if len(testCase.Chunks) == 0 {
		return ""
	}
	quoted := make([]string, len(testCase.Chunks))
	for i, chunk := range testCase.Chunks {
		quoted[i] = fmt.Sprintf("%+q", chunk)
	}
	return ". Chunks: " + strings.Join(quoted, " ")
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
	if text, ok := value.(string); ok {
		return fmt.Sprintf("%+q", text)
	}
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
