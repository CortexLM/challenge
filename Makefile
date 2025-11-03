.PHONY: install install-dev lint format test clean

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check src/
	mypy src/

format:
	ruff format src/
	black src/
	isort src/

test:
	pytest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

check:
	ruff check src/
	black --check src/
	isort --check src/
	python scripts/check_file_length.py

