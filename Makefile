.PHONY: build test run lint typecheck docker-build docker-run clean

build:
	pip install -e .

test:
	pytest -q --cov=back_office_ui --cov-report=xml:coverage.xml

run:
	streamlit run src/back_office_ui/app.py --server.port=8501 --server.address=0.0.0.0

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