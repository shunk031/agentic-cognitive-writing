.PHONY: setup test

setup:
	uv sync
	pre-commit install

test:
	uv run pytest
