"""auth.py – session-based login with bcrypt passwords stored in a JSON file."""
import json, os, time, secrets, bcrypt
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
SESSIONS: dict = {}   # token -> {username, role, expires}
SESSION_TTL = int(os.environ.get("SESSION_TTL_HOURS", "24")) * 3600


def _load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {}


def _save_users(users: dict):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def bootstrap_admin():
    """Create the admin user from env vars if no users exist."""
    users = _load_users()
    if not users:
        username = os.environ.get("ADMIN_USER", "admin")
        password = os.environ.get("ADMIN_PASS", "changeme")
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        users[username] = {"hash": hashed, "role": "admin"}
        _save_users(users)


def login(username: str, password: str):
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    if bcrypt.checkpw(password.encode(), user["hash"].encode()):
        token = secrets.token_hex(32)
        SESSIONS[token] = {
            "username": username,
            "role": user["role"],
            "expires": time.time() + SESSION_TTL,
        }
        return token
    return None


def logout(token: str):
    SESSIONS.pop(token, None)


def get_session(token: str):
    sess = SESSIONS.get(token)
    if sess and sess["expires"] > time.time():
        return sess
    SESSIONS.pop(token, None)
    return None


def require_auth(f):
    """Flask route decorator – requires a valid Bearer token."""
    from functools import wraps
    from flask import request, jsonify

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if not get_session(token):
            return jsonify({"error": "Unauthorised"}), 401
        return f(*args, **kwargs)
    return wrapper
