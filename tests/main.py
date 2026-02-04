"""Simple test runner to execute the test suite from the `tests/` folder.

Run with:

    python tests/main.py

This will invoke pytest programmatically so you can run tests consistently
across environments or from an IDE that prefers a single entrypoint.
"""
import sys

import pytest


def main(argv=None):
    """Run pytest with the provided argv list. Returns pytest exit code."""
    if argv is None:
        argv = ["-v"]
    return pytest.main(argv)


if __name__ == "__main__":
    sys.exit(main())
