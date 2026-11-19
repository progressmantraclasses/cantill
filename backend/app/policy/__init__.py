import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent


def normalise_policy(doc: dict) -> dict:
    """Policy documents are stored as JSON; the engine wants effective_from as a date."""
    p = dict(doc)
    if isinstance(p["effective_from"], str):
        p["effective_from"] = date.fromisoformat(p["effective_from"])
    return p


def load_v5() -> dict:
    return normalise_policy(json.loads((HERE / "v5_0.json").read_text(encoding="utf-8")))
