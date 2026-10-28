# tokenizer-tester

Tester for the [Build your own Tokenizer](https://github.com/codecrafters-io/build-your-own-tokenizer) challenge.

```sh
make test
```

`make test` creates a Python virtualenv, installs `regex` and `tiktoken`, and runs the Go tests. The reference CLI is `internal/test_helpers/scenarios/base/tokenizer.py`. Regenerate frozen outputs with:

```sh
.venv/bin/python scripts/generate_fixtures.py
```
