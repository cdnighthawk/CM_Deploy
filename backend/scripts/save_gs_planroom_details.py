"""Save parsed Online Plan Service detail payloads onto Golden State leads."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env", override=True)

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.golden_state_planroom_detail import apply_detail_updates  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Upsert Golden State planroom detail JSON.")
    parser.add_argument("json_path", help="JSON list of {plan_number, detail}")
    args = parser.parse_args()
    items = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    if isinstance(items, dict) and "items" in items:
        items = items["items"]
    app = create_app()
    with app.app_context():
        updated, skipped = apply_detail_updates(db.session, items)
    print(f"updated {updated} skipped {skipped}")


if __name__ == "__main__":
    main()
