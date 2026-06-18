import json, os, io, socket
from pathlib import Path
from smb.SMBConnection import SMBConnection

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
SHARES_FILE = DATA_DIR / "smb_shares.json"

def _load(): return json.loads(SHARES_FILE.read_text()) if SHARES_FILE.exists() else []
def _save(s): SHARES_FILE.write_text(json.dumps(s, indent=2))
def list_shares(): return _load()

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

def _resolve(host):
    try: return socket.gethostbyaddr(host)[0].split(".")[0].upper()
    except Exception: return host.split(".")[0].upper()

def _conn(cfg):
    host = cfg["host"]
    port = int(cfg.get("port", 445))
    c = SMBConnection(cfg["username"], cfg["password"], "SAGEDRIVE", _resolve(host),
        use_ntlm_v2=True, is_direct_tcp=(port == 445))
    if not c.connect(host, port):
        raise ConnectionError(f"SMB connect failed for {host}:{port}")
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

def stream_file(share_id, path, chunk_size=2*1024*1024):
    cfg = _cfg(share_id)
    host = cfg["host"]
    port = int(cfg.get("port", 445))
    c = SMBConnection(cfg["username"], cfg["password"], "SAGEDRIVE", _resolve(host),
        use_ntlm_v2=True, is_direct_tcp=(port == 445))
    if not c.connect(host, port):
        raise ConnectionError(f"SMB connect failed for {host}:{port}")
    try:
        offset = 0
        while True:
            buf = io.BytesIO()
            bytes_read, _ = c.retrieveFileFromOffset(cfg["share"], path, buf, offset, max_length=chunk_size)
            if bytes_read == 0:
                break
            yield buf.getvalue()
            offset += bytes_read
            if bytes_read < chunk_size:
                break
    finally:
        c.close()

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
