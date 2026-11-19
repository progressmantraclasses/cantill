from __future__ import annotations

import re
import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from .. import models as m
from ..models import Session
from ..seed import load_master_from_db, load_policies_from_db
from ..services import batches as bsvc
from ..services import chat as chatsvc
from ..services.llm import llm
from .common import actor, err

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def _items_and_params():
    md = load_master_from_db(Session)
    pols = load_policies_from_db(Session)
    from ..engine.pipeline import select_policy
    pol = select_policy(pols, bsvc.now_ist().date())
    return md.items, pol["params"].get("matching")


def _save(sess: m.ChatSession, role: str, text: str, extra: dict | None = None):
    sess.messages = list(sess.messages) + [{"role": role, "text": text, **(extra or {})}]
    flag_modified(sess, "messages")
    flag_modified(sess, "slots")


@bp.post("")
def turn():
    body = request.get_json(force=True)
    text = (body.get("message") or "").strip()
    who, _ = actor()
    sid = body.get("session_id")
    sess = Session.get(m.ChatSession, sid) if sid else None
    if sess is None:
        sess = m.ChatSession(id=uuid.uuid4().hex[:16], requester=who, slots={}, messages=[], state="collecting")
        Session.add(sess)
    if not text:
        return err("Say what you need, for example: need 200 nitrile gloves for Chakan by next Friday")
    today = bsvc.now_ist().date()
    items, mparams = _items_and_params()
    slots = dict(sess.slots)
    low = text.lower().strip()
    _save(sess, "user", text)

    if re.fullmatch(r"(cancel|reset|start over|new request|clear)", low):
        sess.slots, sess.state = {}, "collecting"
        _save(sess, "assistant", "Okay, cleared. What do you need to buy?")
        Session.commit()
        return jsonify(_resp(sess, {"reply": "Okay, cleared. What do you need to buy?", "state": "need_item"}))

    state = sess.state
    handled = False
    if state == "choose_item":
        opts = slots.get("options", [])
        pick = None
        if m_ := re.fullmatch(r"\s*#?(\d)\s*\.?", low):
            i = int(m_[1]) - 1
            pick = opts[i]["item_code"] if 0 <= i < len(opts) else None
        elif m_ := re.search(r"ITM-\d{4}", text.upper()):
            pick = m_[0] if m_[0] in items else None
        if pick:
            slots["item_code"] = pick
            handled = True
        elif re.search(r"\b(none|neither|no|other|something else|new)\b", low):
            slots["is_new"], handled = True, True
        slots.pop("options", None)
    elif state == "unknown_item" and re.search(r"\b(new item|yes|new|raise it|go ahead|ok|okay)\b", low):
        slots["is_new"], handled = True, True
        if (x := chatsvc.regex_extract(text)).get("est_unit_price") is not None:
            slots["est_unit_price"] = x["est_unit_price"]
    elif state == "need_estimate":
        if re.search(r"unknown|don'?t know|no idea|not sure|skip", low):
            slots["est_unit_price"] = None
            slots["est_asked"] = True
            handled = True
        elif m_ := re.search(r"(\d[\d,]*(?:\.\d+)?)", text):
            slots["est_unit_price"], handled = float(m_[1].replace(",", "")), True
    elif state == "need_quantity" and (m_ := re.fullmatch(r"\s*(\d[\d,]*(?:\.\d+)?)\s*(?:[a-zA-Z]+)?\s*", text)):
        slots["quantity"], handled = float(m_[1].replace(",", "")), True
    elif state == "need_plant":
        x = chatsvc.regex_extract(text)
        if x.get("plant"):
            slots["plant"], handled = x["plant"], True
    elif state == "need_date":
        d = chatsvc.parse_date(text, today)
        if d:
            slots["need_by"], handled = d.isoformat(), True
    elif state == "confirm" and re.fullmatch(r"(yes|y|ok|okay|confirm|correct|confirmed|go ahead|submit)[.! ]*", low):
        sess.slots = slots
        return _confirm(sess, who)

    if not handled:
        x = chatsvc.extract(text, today, llm)
        # a new item description replaces the old one and clears any earlier item resolution
        if x.get("item_text") and state not in ("confirm",):
            if x["item_text"] != slots.get("item_text"):
                slots.pop("item_code", None)
                slots.pop("is_new", None)
                slots.pop("est_asked", None)
            slots["item_text"] = x["item_text"]
        elif x.get("item_text") and state == "confirm" and re.search(r"ITM-\d{4}|change item", text, re.I):
            slots["item_text"] = x["item_text"]
            slots.pop("item_code", None)
        if m_ := re.search(r"ITM-\d{4}", text.upper()):
            if m_[0] in items:
                slots["item_code"] = m_[0]
                slots.setdefault("item_text", items[m_[0]]["description"])
        for k in ("quantity", "plant", "need_by", "urgency", "est_unit_price"):
            if x.get(k) is not None:
                slots[k] = x[k]
        if state == "confirm":
            if re.search(r"\b(make it|change (?:it )?to|quantity|qty)\b", low) and "quantity" not in x:
                pass
            if re.search(r"\bnot urgent|normal\b", low):
                slots["urgency"] = "Normal"

    step = chatsvc.next_step(slots, items, mparams, today)
    slots["options"] = step.get("options") if step["state"] == "choose_item" else None
    if slots["options"] is None:
        slots.pop("options")
    sess.slots, sess.state = slots, step["state"]
    _save(sess, "assistant", step["reply"], {"card": step.get("card"), "options": step.get("options")})
    Session.commit()
    return jsonify(_resp(sess, step))


def _resp(sess, step):
    return {"session_id": sess.id, "reply": step["reply"], "state": step["state"], "options": step.get("options"),
            "card": step.get("card"), "slots": {k: v for k, v in sess.slots.items() if k != "options"}}


@bp.post("/confirm")
def confirm():
    body = request.get_json(force=True)
    sess = Session.get(m.ChatSession, body.get("session_id") or "")
    if not sess:
        return err("chat session not found", 404)
    who, _ = actor()
    return _confirm(sess, who)


def _confirm(sess: m.ChatSession, who: str):
    slots = sess.slots
    items, _ = _items_and_params()
    step = chatsvc.next_step(dict(slots), items, None, bsvc.now_ist().date())
    if step["state"] != "confirm":
        return jsonify({**_resp(sess, step), "error": "The request is not complete yet."}), 409
    card = step["card"]
    batch = Session.scalar(select(m.Batch).where(m.Batch.kind == "chat"))
    if batch is None:
        batch = m.Batch(name="Chat requests", kind="chat", created_by="chat", lines=[])
        Session.add(batch)
        Session.flush()
    n = len(batch.lines) + 1
    pr_no = f"PR-CH-{n:04d}"
    now = bsvc.now_ist()
    line = {"pr_no": pr_no, "pr_line": 1, "plant": card["plant"],
            "item_code": "" if card["is_new"] else card["item_code"], "description": card["description"],
            "uom": card["uom"], "department": "Chat", "requester": who if who != "anonymous" else (sess.requester or ""),
            "urgency": card["urgency"], "quantity": card["quantity"], "estimated_unit_price": card["est_unit_price"],
            "errors": [], "row": n, "force_new": card["is_new"],
            "created_at": now.isoformat(sep=" "), "need_by": card["need_by"]}
    batch.lines = list(batch.lines) + [line]
    flag_modified(batch, "lines")
    result = bsvc.run_batch(Session, batch)
    req = next(r for r in result["requirements"] if any(l["pr_no"] == pr_no for l in r["lines"]))
    bsvc.audit(Session, who, "Requester", "raise_pr", pr_no, detail={"route": req["route"], "chat": sess.id})
    reply = (f"Raised **{pr_no}**. Procurement policy v{req['policy_version']} says: **{req['route'].replace('_', ' ')}**"
             f" for the whole requirement worth ₹{req['value']:,.0f}. {req['reason']}")
    sess.slots, sess.state = {}, "collecting"
    _save(sess, "assistant", reply, {"decision": {k: req[k] for k in ("route", "decision", "value", "group_id", "reason")}})
    Session.commit()
    return jsonify({"session_id": sess.id, "pr_no": pr_no, "reply": reply, "state": "done", "batch_id": batch.id,
                    "decision": {k: req[k] for k in ("route", "decision", "value", "group_id", "supplier_id",
                                                     "supplier_name", "unit_price", "suggested", "reason", "flags",
                                                     "policy_version")}})


@bp.get("/<sid>")
def history(sid):
    sess = Session.get(m.ChatSession, sid)
    if not sess:
        return err("not found", 404)
    return jsonify({"session_id": sess.id, "messages": sess.messages, "state": sess.state})
