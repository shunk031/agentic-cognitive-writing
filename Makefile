.PHONY: setup test docs-prepare docs-build docs-serve

setup:
	uv sync
	pre-commit install

test:
	uv run pytest

#
# Documentation
#

ZENSICAL_VERSION ?= 0.0.58
ZENSICAL = uv run --no-project --with zensical==$(ZENSICAL_VERSION) --

docs-prepare:
	uv run --no-project -- python tools/build-docs-site.py

docs-build: docs-prepare
	$(ZENSICAL) zensical build --clean --strict

docs-serve: docs-prepare
	$(ZENSICAL) zensical serve
