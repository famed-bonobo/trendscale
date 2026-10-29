"""Shared test helpers: real Google Trends answers captured on 2026-10-17, stored as fixtures."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def fixture_text():
    def read(name: str) -> str:
        return (FIXTURES / f'{name}.txt').read_text(encoding='utf-8')

    return read
