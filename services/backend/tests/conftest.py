"""Pytest configuration and fixture setup."""

import sys
from pathlib import Path

import pytest

# Ensure repo root and services/backend are in sys.path
_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent
_REPO_ROOT = _BACKEND_DIR.parent.parent

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "unit: Unit tests (no external services required)"
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (may require DB or multi-component integration)",
    )
    config.addinivalue_line("markers", "security: Security and injection tests")
