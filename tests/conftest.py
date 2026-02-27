"""Shared pytest configuration and fixtures for the TRXO test suite.

This module provides:
- Common fixtures (temp directories, mock objects, etc.)
- Test configuration (logging, paths, markers)
- Helper utilities for unit and integration tests
"""
import sys
from pathlib import Path

import pytest


# Add src/ to path so test modules can import trxo package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def mock_config():
    """Provide a mock configuration dict for testing."""
    return {
        "auth": {
            "type": "service_account",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        },
        "endpoint": "https://example.auth0.com",
        "realm": "test_realm",
    }


@pytest.fixture
def sample_json_data():
    """Provide sample JSON data for export/import testing."""
    return {
        "id": "test-id-123",
        "name": "Test Resource",
        "description": "A test resource",
        "enabled": True,
        "metadata": {"created": "2024-01-01", "version": "1.0"},
    }


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (slower)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (deselect with '-m \"not slow\"')"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location."""
    for item in items:
        # Mark all tests as unit by default unless they're in specific paths
        if "integration" not in item.nodeid:
            item.add_marker(pytest.mark.unit)
