package fixtures

import "embed"

// FS holds the frozen expected outputs and the GPT-2 vocabulary files.
//
//go:embed *.json gpt2/*
var FS embed.FS
