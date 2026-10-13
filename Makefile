.PHONY: test setup clean

ROOT_DIR := .
GRADING_DIR ?= .grading
GRADE_FILE ?= $(GRADING_DIR)/grade.txt

# Default to skipping grade file generation
GENERATE_GRADE_FILE ?= false
PYTHON_CMD := uv run
PRECOMMIT_CMD := uvx pre-commit@4.1.0

# Default target
.DEFAULT_GOAL := help

# Help command
help:
	@echo "Lab Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make test         Run all tests"
	@echo "  make lint         Run all linters"
	@echo "  make clean        Clean cache files"
	@echo "  make setup        Setup development environment"


# Setup development environment
install-uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv venv

setup: clean install-uv
	@echo "Setting up the environment."
	@echo "TODO: Please uncomment the following lines:"
	# cd $(LAB_DIR) && \
	# if ! command -v uv >/dev/null 2>&1; then \
	# 	echo "uv not found, installing..."; \
	# 	curl -LsSf https://astral.sh/uv/install.sh | sh; \
	# 	export PATH="$$HOME/.cargo/bin:$$PATH"; \
	# fi && \
	# uv venv && \
	# uv add --group dev $(ROOT_DIR)/.vocareum/pytestplugin
	@echo "TODO: Add your development dependencies here!"

# Target to remove the score file before a fresh run
clean-score-file:
	@rm -f $(GRADE_FILE)
	@echo "Removed existing grade file if it existed."	

# Run all tests
test: clean-score-file
	@echo "Executing tests ..."
ifneq ($(GENERATE_GRADE_FILE),false)
	@echo "--- GRADING ENABLED: Creating grade file at $(GRADE_FILE) ---"
	@mkdir -p $(GRADING_DIR)
	
	@echo "Running all tests"
	@echo "TODO: Add your test commands here as in the example below."
	@$(MAKE) test-example
	cat $(GRADE_FILE)
else
	@echo "--- GRADING DISABLED: Skipping grade file creation. ---"
endif	
	@echo "Tests execution completed."

test-example:
	@echo "Running example test ..."
	# Example test command
	# ($(PYTHON_CMD) pytest tests/unit/test_example.py -vv) >> $(GRADE_FILE)

# Run formatting and type checking
lint:
	@echo "Running linters ..."


# Clean cache files
clean:
	@echo "Cleaning up the workspace"