.PHONY: install test lint typecheck check format api demo

install:
	uv sync --locked

test:
	uv run --locked pytest

lint:
	uv run --locked ruff check .
	uv run --locked ruff format . --check

typecheck:
	uv run --locked basedpyright

check: test lint typecheck

format:
	uv run --locked ruff check . --fix
	uv run --locked ruff format .

api:
	uv run --locked uvicorn apps.api.main:app --reload

demo:
	uv run --locked python scripts/demo.py
