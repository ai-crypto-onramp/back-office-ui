.PHONY: build test run run-local lint typecheck docker-build docker-run clean

build:
	pip install -e .

test:
	pytest -q --cov=back_office_ui --cov-report=xml:coverage.xml

run:
	PYTHONPATH=src streamlit run src/back_office_ui/app.py --server.port=8501 --server.address=0.0.0.0

run-local:
	TREASURY_URL=http://localhost:8100 \
	LIQUIDITY_URL=http://localhost:8089 \
	FX_HEDGING_URL=http://localhost:8086 \
	LEDGER_URL=http://localhost:8088 \
	RECONCILIATION_URL=http://localhost:8098 \
	WALLET_URL=http://localhost:8101 \
	PAYMENT_URL=http://localhost:8094 \
	MPC_URL=http://localhost:8091 \
	PRICING_URL=http://localhost:8096 \
	NOTIFICATION_URL=http://localhost:8092 \
	PYTHONPATH=src streamlit run src/back_office_ui/app.py --server.port=8501 --server.address=0.0.0.0

lint:
	ruff check src tests

typecheck:
	mypy src/back_office_ui

docker-build:
	docker build -t ai-crypto-onramp/back-office-ui .

docker-run:
	docker run --rm -p 8501:8501 ai-crypto-onramp/back-office-ui

clean:
	rm -rf dist build *.egg-info .pytest_cache coverage.xml .coverage htmlcov