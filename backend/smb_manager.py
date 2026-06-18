import json, os, io, socket
from pathlib import Path
from smb.SMBConnection import SMBConnection

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
SHARES_FILE = DATA_DIR / "smb_shares.json"

def _load(): return json.loads(SHARES_FILE.read_text()) if SHARES_FILE.exists() else []
def _save(s): SHARES_FILE.write_text(json.dumps(s, indent=2))

def list_shares():
    return _load()

def add_share(name, host, share, username, password, port=445):
    sid = name.lower().replace(" ", "_")
    shares = [s for s in _load() if s["id"] != sid]
    entry = {"id": sid, "name": name, "host": host, "share": share,
             "username": username, "password": password, "port": port}
    shares.append(entry)
    _save(shares)
    return entry

def remove_share(share_id):
    _save([s for s in _load() if s["id"] != share_id])

def _conn(cfg):
    host = cfg["host"]
    port = int(cfg.get("port", 445))
    try:
        remote_name = socket.gethostbyaddr(host)[0].split(".")[0].upper()
    except Exception:
        remote_name = host.split(".")[0].upper()
    c = SMBConnection(
        cfg["username"], cfg["password"],
        "SAGEDRIVE", remote_name,
        use_ntlm_v2=True,
        is_direct_tcp=(port == 445),
    )
    connected = c.connect(host, port)
    if not connected:
        raise ConnectionError(
            f"SMB connect failed for {host}:{port} (remote_name={remote_name!r}). "
            "Check credentials, share name, and that SMB2/3 is enabled."
        )
    return c

def _cfg(share_id):
    s = {s["id"]: s for s in _load()}.get(share_id)
    if not s: raise ValueError(f"Share {share_id!r} not found")
    return s

def browse(share_id, path="/"):
    cfg = _cfg(share_id)
    c = _conn(cfg)
    try:
        return [{"name": e.filename, "type": "folder" if e.isDirectory else "file",
                 "size": e.file_size, "modified": e.last_write_time,
                 "path": path.rstrip("/") + "/" + e.filename}
                for e in c.listPath(cfg["share"], path) if e.filename not in (".", "..")]
    finally: c.close()

def download_file(share_id, path):
    cfg = _cfg(share_id)
    c = _conn(cfg)
    buf = io.BytesIO()
    try:
        c.retrieveFile(cfg["share"], path, buf)
        return buf.getvalue(), path.split("/")[-1]
    finally: c.close()

def upload_file(share_id, dest_path, data):
    cfg = _cfg(share_id)
    c = _conn(cfg)
    try: c.storeFile(cfg["share"], dest_path, io.BytesIO(data))
    finally: c.close()

def delete_path(share_id, path, is_dir=False):
    cfg = _cfg(share_id)
    c = _conn(cfg)
    try:
        if is_dir: c.deleteDirectory(cfg["share"], path)
        else: c.deleteFiles(cfg["share"], path)
    finally: c.close()

def create_directory(share_id, path):
    cfg = _cfg(share_id)
    c = _conn(cfg)
    try: c.createDirectory(cfg["share"], path)
    finally: c.close()
