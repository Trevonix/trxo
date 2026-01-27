# Contributing to TRXO

Thank you for your interest in contributing to TRXO! Contributions are welcome and appreciated, whether they are bug reports, code changes, documentation improvements, or feature ideas.

## Ways to Contribute

- Report bugs and issues.  
- Propose and implement new features.  
- Improve documentation and examples.  
- Add or improve tests.  
- Help triage issues and review pull requests.

## Getting Started

### Prerequisites

- Python 3.8+  
- `git`  
- A GitHub account (for submitting issues and pull requests)

### Development Setup

1. **Fork** the repository on GitHub and clone your fork:

   ```bash
   git clone https://github.com/<your-username>/trxo.git
   cd trxo
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode**:

   ```bash
   pip install -e ".[dev]"
   ```

4. **Run tests** to verify everything is working:

   ```bash
   pytest
   ```

## Coding Guidelines

- Follow the existing code style; we aim to use:
  - `black` for formatting.
  - `isort` for import ordering.
  - `ruff` or `flake8` for linting.
  - `mypy` for type checking where possible.
- Add type hints for new public functions and classes.
- Write clear docstrings for public APIs and complex logic.
- Keep functions small and focused where possible.

## Tests

- Add or update tests for any behavior changes.
- Ensure `pytest` passes before submitting a PR.
- Prefer unit tests for utilities and integration tests for full flows (export/import/batch).

## Submitting a Pull Request

1. **Create a feature branch**:

   ```bash
   git checkout -b feature/my-new-feature
   ```

2. Make your changes and add tests where appropriate.

3. Run linters and tests:

   ```bash
   black src tests
   isort src tests
   pytest
   ```

4. Commit your changes with a clear message:

   ```bash
   git commit -am "Add support for XYZ"
   ```

5. Push your branch:

   ```bash
   git push origin feature/my-new-feature
   ```

6. Open a **Pull Request** against the main repository:
   - Describe what the change does.
   - Link to any related issues (e.g. “Closes #123”).
   - Explain any breaking changes or migration steps.

## Reporting Bugs and Requesting Features

- Use GitHub **Issues**.  
- For bugs, include:
  - Steps to reproduce.
  - Expected vs actual behavior.
  - Environment details (OS, Python version, TRXO version).
- For feature requests, explain:
  - The problem you’re facing.
  - How the feature would help.
  - Any API/UX ideas you have.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT).