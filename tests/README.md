# TRXO Test Suite

Professional unit and integration test suite for the TRXO (PingOne Configuration Management Tool).

## Quick Start

### Run All Tests
```bash
pytest -v
```

### Run from Python
```bash
python trxo/tests/main.py
```

## Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── main.py                     # Test runner entrypoint
├── trxo/
│   ├── auth/                  # Tests for auth modules
│   ├── commands/
│   │   ├── batch/            # Batch operations tests
│   │   ├── config/           # Configuration tests
│   │   ├── export/           # Export command tests
│   │   ├── imports/          # Import command tests
│   │   └── utils/            # Utilities tests (diff, export, git, imports)
│   ├── logging/              # Logging tests
│   └── utils/                # Base utilities tests
└── README.md                 # This file
```

## Available Markers

Run specific test categories:

```bash
# Unit tests only (fast, no dependencies)
pytest -m unit -v

# Integration tests only
pytest -m integration -v

# Skip slow tests
pytest -m "not slow" -v
```

## Writing Tests

### Basic Test Example
```python
"""Tests for module_name"""
import pytest
from trxo.module import function


def test_function_returns_expected_value():
    """Test that function returns expected value."""
    result = function(input_data)
    assert result == expected_value


def test_function_raises_on_invalid_input(mock_config):
    """Test that function raises exception on invalid input."""
    with pytest.raises(ValueError):
        function(invalid_input)
```

### Using Fixtures
Common fixtures are available in `conftest.py`:
- `temp_dir`: Temporary directory for file I/O tests
- `mock_config`: Pre-configured mock configuration dict
- `sample_json_data`: Sample JSON for export/import tests

```python
def test_with_temp_dir(temp_dir):
    """Test that uses temporary directory."""
    test_file = temp_dir / "test.json"
    test_file.write_text("{}")
    assert test_file.exists()


def test_with_config(mock_config):
    """Test that uses mock configuration."""
    assert mock_config["auth"]["type"] == "service_account"
```

## Running Tests with Coverage

Install pytest-cov:
```bash
pip install pytest-cov
```

Run with coverage:
```bash
pytest --cov=src/trxo --cov-report=html -v
```

## Continuous Integration

Tests are configured to run automatically on:
- Local commits (if pre-commit hooks are set up)
- Push to repository
- Pull requests

## Troubleshooting

### Import Errors
Ensure you're running from the repository root:
```bash
cd /path/to/TRXO
pytest -v
```

### Fixture Not Found
Check that `conftest.py` is in the `tests/` directory and is properly formatted.

### Tests Not Discovered
Verify test files follow naming convention: `test_*.py` or `*_test.py`

## Contributing

When adding new tests:
1. Create test file in appropriate subdirectory matching source structure
2. Add docstrings to all test functions
3. Use meaningful assertion messages
4. Mark as `@pytest.mark.unit` or `@pytest.mark.integration` if needed
5. Run full suite before submitting: `pytest -v`
