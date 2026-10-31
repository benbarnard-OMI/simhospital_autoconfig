.PHONY: validate-simulator test lint

test:
	python -m pytest -v

lint:
	python -m pip install ruff
	ruff check simhospital_autoconfig tests

validate-simulator:
	bash scripts/generate_and_validate.sh 1730209545
