.PHONY: setup test

setup:
	uv sync
	uv run pre-commit install

test:
	uv run pytest
