.PHONY: test copy_course_file build

test: .venv/bin/python
	go test -count=1 ./internal/...

build:
	go build -o dist/main.out ./cmd/tester

copy_course_file:
	cp ../build-your-own-tokenizer/course-definition.yml internal/test_helpers/course_definition.yml

.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
