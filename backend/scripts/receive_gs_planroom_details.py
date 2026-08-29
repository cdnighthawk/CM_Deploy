"""Temporary CORS-open receiver so the signed-in planroom tab can POST details."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv(_ROOT / ".env", override=True)

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.golden_state_planroom_detail import apply_detail_updates  # noqa: E402
from app.models.golden_state_planroom_lead import GoldenStatePlanroomLead  # noqa: E402
from sqlalchemy import select  # noqa: E402

usis = create_app()
app = Flask(__name__)
CORS(app, origins="*")


@app.get("/pending")
def pending():
    try:
        limit = max(1, min(int(request.args.get("limit", 40)), 100))
    except ValueError:
        limit = 40
    with usis.app_context():
        rows = db.session.scalars(select(GoldenStatePlanroomLead)).all()
        waiting = [
            {"plan_number": row.plan_number, "url": row.project_url}
            for row in rows
            if row.project_url and not row.detail
        ]
        done = sum(1 for row in rows if row.detail)
    return jsonify({"items": waiting[:limit], "remaining": len(waiting), "done": done, "total": len(rows)})


@app.post("/details")
def details():
    body = request.get_json(silent=True) or {}
    items = body.get("items") or body
    if not isinstance(items, list):
        return jsonify({"error": "items list required"}), 400
    with usis.app_context():
        updated, skipped = apply_detail_updates(db.session, items)
    return jsonify({"updated": updated, "skipped": skipped})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=False)
