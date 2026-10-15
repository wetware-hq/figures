"""The one approved clock. Mode is set explicitly by the caller's environment:
FIGURES_CLOCK=test -> the scenario clock in FIGURES_SCENARIO_CLOCK (ISO time); FIGURES_CLOCK=real -> the real clock.
Anything else refuses with RF-CLOCK-UNSET (text from the signed wording; none until the row is signed)."""
import os
from datetime import datetime


class ClockUnset(Exception):
    def __init__(self):
        from wording import LINES
        self.line_id, self.text = "RF-CLOCK-UNSET", LINES.get("RF-CLOCK-UNSET", "")
        super().__init__(self.line_id)


def now():
    mode = os.environ.get("FIGURES_CLOCK")
    if mode == "real":
        return datetime.now()
    if mode == "test" and os.environ.get("FIGURES_SCENARIO_CLOCK"):
        return datetime.fromisoformat(os.environ["FIGURES_SCENARIO_CLOCK"])
    raise ClockUnset()
