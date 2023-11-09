.PHONY: run test clean setup lint
run:
	./venv/bin/python srpusher.py

lint:
	./venv/bin/flake8 srpusher.py

test:
	./venv/bin/python tests.py

clean:
	find . -name "*.py[co]" -delete
	rm -rf venv __pycache__ .mypy_cache

setup:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt
