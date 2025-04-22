# Makefile for code formatting and linting

.PHONY: help format check-tools install-tools

# Default target when just running 'make'
help:
	@echo "Available targets:"
	@echo "  format      - Format all C++/C/Cython code using clang-format"
	@echo "  lint        - Lint Cython files with cython-lint"
	@echo "  check-tools - Check if required formatting tools are installed"
	@echo "  install-tools - Install required formatting tools (macOS only)"

# Check if the required tools are installed
check-tools:
	@echo "Checking for required tools..."
	@which clang-format >/dev/null 2>&1 || \
		{ echo "clang-format is not installed. On macOS use 'brew install clang-format'"; \
		  echo "On Linux use 'apt-get install clang-format'"; \
		  echo "Or run 'make install-tools' on macOS"; exit 1; }
	@which cython-lint >/dev/null 2>&1 || \
		{ echo "cython-lint is not installed. Install with 'pip install cython-lint'"; \
		  echo "Or run 'make install-tools'"; exit 1; }
	@echo "All required tools are installed."

# Install tools on macOS
install-tools:
	@echo "Installing required tools..."
	@if [ "$(shell uname)" = "Darwin" ]; then \
		echo "Detected macOS. Installing tools via Homebrew..."; \
		brew install clang-format || echo "Failed to install clang-format. Please install manually."; \
		pip install cython-lint || echo "Failed to install cython-lint. Please install manually."; \
	else \
		echo "This command only works on macOS. Please install tools manually:"; \
		echo "  - clang-format: apt-get install clang-format (Linux) or brew install clang-format (macOS)"; \
		echo "  - cython-lint: pip install cython-lint"; \
	fi

# Format all C/C++/Cython code
format: check-tools
	@echo "Formatting C/C++/Cython code with clang-format..."
	@find . -type f \( -name "*.c" -o -name "*.h" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.pyx" -o -name "*.pxd" \) \
		-not -path "*/\.*" -not -path "*/build/*" -not -path "*/venv/*" -not -path "*/dist/*" \
		-exec echo "Formatting {}" \; \
		-exec clang-format -i {} \;
	@echo "Formatting complete."

# Lint Cython files
lint: check-tools
	@echo "Linting Cython files with cython-lint..."
	@find . -type f \( -name "*.pyx" -o -name "*.pxd" \) \
		-not -path "*/\.*" -not -path "*/build/*" -not -path "*/venv/*" -not -path "*/dist/*" \
		-exec echo "Linting {}" \; \
		-exec cython-lint {} \;
	@echo "Linting complete."

# Combined format and lint
all: format lint
	@echo "All formatting and linting tasks completed."