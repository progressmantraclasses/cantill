"""Manual PR form: raise one purchase request without the chat assistant."""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..database import Session
from ..repository import load_master_from_db
from ..services import batches as bsvc
from ..services import requests as reqsvc
from .common import actor, json_body

bp = Blueprint("requests", __name__, url_prefix="/api/prs")


@bp.post("")
def raise_manual_pr():
    """Body: {item_code | is_new + description + uom, quantity, plant, need_by, urgency?, est_unit_price?}."""
    who, role = actor()
    md = load_master_from_db(Session)
    card, errors = reqsvc.card_from_form(json_body(), md.items, md.plants, bsvc.now_ist().date())
    if errors:
        return jsonify({"error": "The request is not complete.", "errors": errors}), 422
    out = reqsvc.raise_pr(Session, card, who if who != "anonymous" else "", channel="form")
    req = out["requirement"]
    bsvc.audit(Session, who, role, "raise_pr", out["pr_no"], detail={"route": req["route"], "channel": "form"})
    Session.commit()
    return jsonify({"pr_no": out["pr_no"], "batch_id": out["batch_id"], "card": card,
                    "reply": reqsvc.decision_reply(out["pr_no"], req), "decision": out["decision"]})
