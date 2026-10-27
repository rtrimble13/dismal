# Developer shortcuts. Requires `uv` (https://docs.astral.sh/uv/).
.PHONY: help venv install lint format typecheck test check build clean release-dry release

PY ?= 3.12

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

venv: ## Create a virtualenv in .venv
	uv venv --python $(PY)

install: venv ## Install the package (editable) with dev dependencies
	uv pip install -e ".[dev]"

lint: ## Ruff lint + format check
	uv run ruff check src tests
	uv run ruff format --check src tests

format: ## Auto-format and fix lint
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck: ## Mypy
	uv run mypy

test: ## Pytest with coverage
	uv run pytest --cov --cov-report=term-missing

check: lint typecheck test ## Everything CI runs

build: ## Build sdist + wheel into dist/
	uv build

clean: ## Remove build artifacts and caches
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache coverage.xml .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

release-dry: ## Show the next patch/minor/major tags without changing anything
	@echo "current: $$(python3 scripts/next_version.py --current)"
	@echo "patch:   $$(python3 scripts/next_version.py patch)"
	@echo "minor:   $$(python3 scripts/next_version.py minor)"
	@echo "major:   $$(python3 scripts/next_version.py major)"

BUMP ?= patch
release: ## Tag the next version locally (BUMP=patch|minor|major) - push the tag to publish
	@TAG="$$(python3 scripts/next_version.py $(BUMP))"; \
	python3 scripts/changelog_release.py "$$TAG" && \
	git add CHANGELOG.md && git commit -m "Release $$TAG" && \
	git tag -a "$$TAG" -m "Release $$TAG" && \
	echo "Created $$TAG. Publish with: git push origin main $$TAG"
