.PHONY: install install-dev setup clean run

# Default Python command
PYTHON := python3
PIP := pip3

# Installation target for production
install:
	$(PIP) install -r requirements.txt

# Installation with development dependencies
install-dev:
	$(PIP) install -r requirements.txt
	$(PIP) install pytest black flake8 mypy

# Create virtual environment and install dependencies
setup:
	$(PYTHON) -m venv venv
	. venv/bin/activate && $(PIP) install --upgrade pip && $(PIP) install -r requirements.txt

# Clean up cached files and temporary data
clean:
	rm -rf __pycache__/
	rm -rf */__pycache__/
	rm -rf *.pyc
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf results_*.md results_*.json crawl_*.md crawl_*.json

# Run the Streamlit application
run:
	streamlit run app.py

# Run the Deep Research Agent from command line (accepts additional args)
research:
	$(PYTHON) main.py $(filter-out $@,$(MAKECMDGOALS))

# Help information
help:
	@echo "Available commands:"
	@echo "  make install      - Install required packages"
	@echo "  make install-dev  - Install required packages including development tools"
	@echo "  make setup        - Create a virtual environment and install dependencies"
	@echo "  make clean        - Clean up cached files and temporary data"
	@echo "  make run          - Run the Streamlit web application"
	@echo "  make research     - Run the Deep Research Agent from command line"
	@echo "  make help         - Show this help message" 