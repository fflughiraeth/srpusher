.PHONY: run test clean setup lint
run:
	./venv/bin/python run_srpusher.py

lint:
	./venv/bin/flake8 run_srpusher.py srpusher.py srpusher_plugin_console.py

test:
	./venv/bin/python tests.py

clean:
	find . -name "*.py[co]" -delete
	rm -rf venv __pycache__ .mypy_cache

setup:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt
