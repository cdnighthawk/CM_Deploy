"""Environment tweaks for ``python scripts/...`` entry points."""
from __future__ import annotations

import os


def skip_startup_lead_bootstrap() -> None:
    """Prevent ``create_app`` from auto-importing BC CSV / demo-seeding (scripts manage data explicitly)."""
    os.environ["USIS_BOOTSTRAP_LEADS_ON_STARTUP"] = "0"
