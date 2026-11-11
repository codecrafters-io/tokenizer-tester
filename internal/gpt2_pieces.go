package internal

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"sync"

	"github.com/codecrafters-io/tokenizer-tester/internal/fixtures"
)

// maxPiecesShown is the longest id list the tester spells out as pieces. A
// longer list is left out rather than clipped, since the piece a learner needs
// is as likely to be past the clip as before it.
const maxPiecesShown = 16

var (
	gpt2TokensOnce sync.Once
	gpt2Tokens     map[int]string
	gpt2TokensErr  error
)

// gpt2ByteOf maps each character GPT-2's files use back to the byte it stands
// for. Bytes 33-126, 161-172, and 174-255 are stored as themselves. The other
// 68, in increasing order, are stored as U+0100 and upward.
func gpt2ByteOf() map[rune]byte {
	table := make(map[rune]byte, 256)
	next := rune(256)
	for b := 0; b < 256; b++ {
		printable := (b >= 33 && b <= 126) || (b >= 161 && b <= 172) || (b >= 174 && b <= 255)
		if printable {
			table[rune(b)] = byte(b)
			continue
		}
		table[next] = byte(b)
		next++
	}
	return table
}

func loadGPT2Tokens() (map[int]string, error) {
	gpt2TokensOnce.Do(func() {
		raw, err := fixtures.FS.ReadFile("gpt2/vocab.json")
		if err != nil {
			gpt2TokensErr = err
			return
		}
		var vocab map[string]int
		if err := json.Unmarshal(raw, &vocab); err != nil {
			gpt2TokensErr = err
			return
		}
		byteOf := gpt2ByteOf()
		gpt2Tokens = make(map[int]string, len(vocab))
		for token, id := range vocab {
			piece := make([]byte, 0, len(token))
			for _, char := range token {
				b, ok := byteOf[char]
				if !ok {
					// <|endoftext|> is the one entry that isn't made of bytes.
					piece = []byte(token)
					break
				}
				piece = append(piece, b)
			}
			gpt2Tokens[id] = string(piece)
		}
	})
	return gpt2Tokens, gpt2TokensErr
}

// gpt2Pieces returns the text of each id in GPT-2's vocabulary, quoted. A
// piece that stops partway through a character keeps its raw bytes, shown as
// \x escapes. ok is false when value isn't a list of GPT-2 ids, or is too long
// to show whole.
func gpt2Pieces(value any) (pieces []string, ok bool) {
	items, isList := value.([]any)
	if !isList || len(items) == 0 || len(items) > maxPiecesShown {
		return nil, false
	}
	tokens, err := loadGPT2Tokens()
	if err != nil {
		return nil, false
	}
	for _, item := range items {
		number, isNumber := item.(json.Number)
		if !isNumber {
			return nil, false
		}
		id, err := strconv.Atoi(number.String())
		if err != nil {
			return nil, false
		}
		piece, known := tokens[id]
		if !known {
			return nil, false
		}
		pieces = append(pieces, strconv.Quote(piece))
	}
	return pieces, true
}

// piecesLine is what the tester logs after a GPT-2 case passes.
func piecesLine(ids any) (string, bool) {
	pieces, ok := gpt2Pieces(ids)
	if !ok {
		return "", false
	}
	return fmt.Sprintf("GPT-2's pieces for %s: %s", preview(ids), strings.Join(pieces, " ")), true
}

// piecesSuffix is added to a GPT-2 case's failure, so a learner can see which
// piece of text their ids split differently.
func piecesSuffix(expected, actual any) string {
	suffix := ""
	if pieces, ok := gpt2Pieces(expected); ok {
		suffix += "\nExpected pieces: " + strings.Join(pieces, " ")
	}
	if pieces, ok := gpt2Pieces(actual); ok {
		suffix += "\nYour pieces:     " + strings.Join(pieces, " ")
	}
	return suffix
}

// gpt2OneIDPerByte is what a program prints when it looks every byte up in
// vocab.json and never merges: the id of each byte's own token, in order.
func gpt2OneIDPerByte(text string) ([]any, bool) {
	tokens, err := loadGPT2Tokens()
	if err != nil || text == "" {
		return nil, false
	}
	idOf := make(map[byte]int, 256)
	for id, piece := range tokens {
		if len(piece) == 1 {
			idOf[piece[0]] = id
		}
	}
	ids := make([]any, len(text))
	for i, b := range []byte(text) {
		id, ok := idOf[b]
		if !ok {
			return nil, false
		}
		ids[i] = json.Number(strconv.Itoa(id))
	}
	return ids, true
}
