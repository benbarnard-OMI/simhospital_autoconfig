.PHONY: validate-simulator test-simulator-e2e test lint

test:
	python -m pytest -v

lint:
	ruff check simhospital_autoconfig tests scripts/run_simulator_e2e.py

validate-simulator:
	bash scripts/generate_and_validate.sh 1730209545

test-simulator-e2e:
	python3 scripts/run_simulator_e2e.py
