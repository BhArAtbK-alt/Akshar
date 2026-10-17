import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    """Every test gets its own empty config dir — never touches ~/.config/akshar."""
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("AKSHAR_CONFIG_DIR", d)
        yield d
