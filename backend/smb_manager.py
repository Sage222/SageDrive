"""smb_manager.py – store/retrieve SMB share configs and list/read/write files."""
import json, os, io
from pathlib import Path
from smb.SMBConnection import SMBConnection

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
SHARES_FILE = DATA_DIR / "smb_shares.json"


def _load_shares() -> list:
    if SHARES_FILE.exists():
        return json.loads(SHARES_FILE.read_text())
    return []


def _save_shares(shares: list):
    SHARES_FILE.write_text(json.dumps(shares, indent=2))


def list_shares() -> list:
    return _load_shares()


def add_share(name: str, host: str, share: str, username: str, password: str, port: int = 445) -> dict:
    shares = _load_shares()
    entry = {
        "id": name.lower().replace(" ", "_"),
        "name": name,
        "host": host,
        "share": share,
        "username": username,
        "password": password,
        "port": port,
    }
    shares = [s for s in shares if s["id"] != entry["id"]]
    shares.append(entry)
    _save_shares(shares)
    return entry


def remove_share(share_id: str):
    shares = [s for s in _load_shares() if s["id"] != share_id]
    _save_shares(shares)


def _connect(cfg: dict) -> SMBConnection:
    conn = SMBConnection(
        cfg["username"], cfg["password"],
        "sagedrive", cfg["host"],
        use_ntlm_v2=True
    )
    conn.connect(cfg["host"], cfg["port"])
    return conn


def browse(share_id: str, path: str = "/") -> list:
    shares = {s["id"]: s for s in _load_shares()}
    cfg = shares.get(share_id)
    if not cfg:
        raise ValueError(f"Share '{share_id}' not found")
    conn = _connect(cfg)
    try:
        entries = conn.listPath(cfg["share"], path)
        result = []
        for e in entries:
            if e.filename in (".", ".."):
                continue
            result.append({
                "name": e.filename,
                "type": "folder" if e.isDirectory else "file",
                "size": e.file_size,
                "modified": e.last_write_time,
                "path": path.rstrip("/") + "/" + e.filename,
            })
        return result
    finally:
        conn.close()


def download_file(share_id: str, path: str):
    shares = {s["id"]: s for s in _load_shares()}
    cfg = shares.get(share_id)
    if not cfg:
        raise ValueError(f"Share '{share_id}' not found")
    conn = _connect(cfg)
    buf = io.BytesIO()
    try:
        conn.retrieveFile(cfg["share"], path, buf)
        filename = path.split("/")[-1]
        return buf.getvalue(), filename
    finally:
        conn.close()


def upload_file(share_id: str, dest_path: str, data: bytes):
    shares = {s["id"]: s for s in _load_shares()}
    cfg = shares.get(share_id)
    if not cfg:
        raise ValueError(f"Share '{share_id}' not found")
    conn = _connect(cfg)
    try:
        conn.storeFile(cfg["share"], dest_path, io.BytesIO(data))
    finally:
        conn.close()


def delete_path(share_id: str, path: str, is_dir: bool = False):
    shares = {s["id"]: s for s in _load_shares()}
    cfg = shares.get(share_id)
    if not cfg:
        raise ValueError(f"Share '{share_id}' not found")
    conn = _connect(cfg)
    try:
        if is_dir:
            conn.deleteDirectory(cfg["share"], path)
        else:
            conn.deleteFiles(cfg["share"], path)
    finally:
        conn.close()


def create_directory(share_id: str, path: str):
    shares = {s["id"]: s for s in _load_shares()}
    cfg = shares.get(share_id)
    if not cfg:
        raise ValueError(f"Share '{share_id}' not found")
    conn = _connect(cfg)
    try:
        conn.createDirectory(cfg["share"], path)
    finally:
        conn.close()
