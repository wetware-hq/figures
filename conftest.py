"""Every figures test runs on an explicit clock: test mode with a synthetic 1930s scenario time (tests that check the
unset or real modes change it themselves)."""
import pytest


@pytest.fixture(autouse=True)
def _scenario_clock(monkeypatch):
    monkeypatch.setenv("FIGURES_CLOCK", "test")
    monkeypatch.setenv("FIGURES_SCENARIO_CLOCK", "1937-10-16T08:00:00")
