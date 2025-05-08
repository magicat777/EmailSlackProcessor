# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test Commands
- Run Python script: `python script_name.py`
- Run a single test: `pytest test_file.py::test_function_name -v`
- Run all tests: `pytest`
- Lint Python code: `flake8 path/to/file.py`
- Type checking: `mypy path/to/file.py`

## Code Style Guidelines
- **Formatting**: Follow PEP 8 guidelines
- **Imports**: Group imports (standard library first, then third-party, then local)
- **Type Hints**: Use type annotations for function parameters and return values
- **Naming Conventions**: 
  - Use `snake_case` for variables and functions
  - Use `CamelCase` for classes
  - Use `UPPER_CASE` for constants
- **Error Handling**: Use try/except blocks with specific exceptions
- **Documentation**: Use docstrings for all functions, classes, and modules
- **Code Structure**: Keep functions focused on a single responsibility
- **Indentation**: 4 spaces (no tabs)