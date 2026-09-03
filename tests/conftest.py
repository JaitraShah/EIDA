"""Test config.

The core suite is offline and fast. Tests marked `@pytest.mark.nli` load a
~1.4 GB NLI model and run real inference; they are skipped unless `--run-nli` is
passed.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-nli", action="store_true", default=False,
        help="run tests that need a downloaded NLI model",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "nli: needs a downloaded NLI model (slow)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-nli"):
        return
    skip = pytest.mark.skip(reason="needs --run-nli")
    for item in items:
        if "nli" in item.keywords:
            item.add_marker(skip)
