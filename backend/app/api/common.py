from flask import request, jsonify


def actor() -> tuple[str, str]:
    """No real auth (see DECISIONS.md): the UI sends the picked name + role; both are audited."""
    return (request.headers.get("X-User", "").strip() or "anonymous",
            request.headers.get("X-Role", "").strip() or "Buyer")


def err(message: str, status: int = 400, **extra):
    return jsonify({"error": message, **extra}), status


def require_role(*roles):
    _, role = actor()
    if role not in roles:
        return err(f"This action needs the {' or '.join(roles)} role (you are acting as {role}).", 403)
    return None
