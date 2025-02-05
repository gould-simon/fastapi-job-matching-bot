#!/bin/bash

# Install test dependencies
pip install -r requirements-test.txt

# Run tests with coverage
pytest tests/ -v --cov=app --cov-report=term-missing 