import os, json, mimetypes, io
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory, redirect
from flask_cors import CORS
import auth, smb_manager, gdrive_manager

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app, supports_credentials=True)
auth.bootstrap_admin()

# ── SPA catch-all ─────────────────────────────────────────────────────────────
@app.route("/", defaults={"path": ""}, methods=["GET"])
@app.route("/<path:path>", methods=["GET"])
def spa(path):
    static = Path(app.static_folder)
    target = static / path
    if path and target.exists():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
def api_login():
    body = request.get_json(force=True) or {}
    u = body.get("username","")
    pw = body.get("password","")
    print(f"LOGIN DEBUG username={u!r} pass_len={len(pw)} keys={list(body.keys())}", flush=True)
    token = auth.login(u, pw)
    if token:
        return jsonify({"token": token})
    return jsonify({"error": "Invalid credentials"}), 401

@app.post("/api/auth/logout")
@auth.require_auth
def api_logout():
    t = request.headers.get("Authorization","").removeprefix("Bearer ").strip()
    auth.logout(t)
    return jsonify({"ok": True})

@app.get("/api/auth/me")
@auth.require_auth
def api_me():
    t = request.headers.get("Authorization","").removeprefix("Bearer ").strip()
    s = auth.get_session(t)
    return jsonify({"username": s["username"], "role": s["role"]})

# ── SMB ───────────────────────────────────────────────────────────────────────
@app.get("/api/smb/shares")
@auth.require_auth
def smb_list_shares():
    return jsonify([{k:v for k,v in s.items() if k != "password"}
                    for s in smb_manager.list_shares()])

@app.post("/api/smb/shares")
@auth.require_auth
def smb_add_share():
    b = request.get_json(force=True) or {}
    try:
        entry = smb_manager.add_share(
            name=b["name"], host=b["host"], share=b["share"],
            username=b.get("username",""), password=b.get("password",""),
            port=int(b.get("port", 445)))
        return jsonify({k:v for k,v in entry.items() if k != "password"}), 201
    except (KeyError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

@app.delete("/api/smb/shares/<share_id>")
@auth.require_auth
def smb_delete_share(share_id):
    smb_manager.remove_share(share_id)
    return jsonify({"ok": True})

@app.get("/api/smb/browse/<share_id>")
@auth.require_auth
def smb_browse(share_id):
    path = request.args.get("path", "/")
    try:
        return jsonify(smb_manager.browse(share_id, path))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/smb/download/<share_id>")
@auth.require_auth
def smb_download(share_id):
    import os, re as _re
    path = request.args.get("path", "")
    try:
        tmp_path, filename, file_size = smb_manager.retrieve_to_tmpfile(share_id, path)
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        range_header = request.headers.get("Range")
        if range_header:
            m = _re.match(r"bytes=(\d+)-(\d*)", range_header)
            start = int(m.group(1)) if m else 0
            end   = int(m.group(2)) if m and m.group(2) else file_size - 1
            end   = min(end, file_size - 1)
            length = end - start + 1
            def stream_range():
                with open(tmp_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining:
                        chunk = f.read(min(65536, remaining))
                        if not chunk: break
                        remaining -= len(chunk)
                        yield chunk
                os.unlink(tmp_path)
            resp = app.response_class(stream_range(), status=206, mimetype=mime)
            resp.headers["Content-Range"]  = f"bytes {start}-{end}/{file_size}"
            resp.headers["Content-Length"] = str(length)
            resp.headers["Accept-Ranges"]  = "bytes"
            resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"' if request.args.get("dl") else f'inline; filename="{filename}"'
            return resp
        else:
            def stream_full():
                with open(tmp_path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk: break
                        yield chunk
                os.unlink(tmp_path)
            resp = app.response_class(stream_full(), mimetype=mime)
            resp.headers["Content-Length"]      = str(file_size)
            resp.headers["Accept-Ranges"]       = "bytes"
            resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"' if request.args.get("dl") else f'inline; filename="{filename}"'
            return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/smb/upload/<share_id>")
@auth.require_auth
def smb_upload(share_id):
    dest = request.args.get("path", "/")
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400
    try:
        smb_manager.upload_file(share_id, dest.rstrip("/") + "/" + f.filename, f.read())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.delete("/api/smb/delete/<share_id>")
@auth.require_auth
def smb_delete_file(share_id):
    b = request.get_json(force=True) or {}
    try:
        smb_manager.delete_path(share_id, b.get("path",""), b.get("is_dir", False))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/smb/mkdir/<share_id>")
@auth.require_auth
def smb_mkdir(share_id):
    b = request.get_json(force=True) or {}
    try:
        smb_manager.create_directory(share_id, b.get("path",""))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Google Drive ──────────────────────────────────────────────────────────────
@app.get("/api/gdrive/status")
@auth.require_auth
def gdrive_status():
    return jsonify({"configured": gdrive_manager.is_configured(),
                    "authenticated": gdrive_manager.is_authenticated()})

@app.get("/api/gdrive/config")
@auth.require_auth
def gdrive_get_config():
    return jsonify(gdrive_manager.get_config())

@app.post("/api/gdrive/config")
@auth.require_auth
def gdrive_save_config():
    b = request.get_json(force=True) or {}
    cfg = gdrive_manager.save_config(
        b.get("client_id", ""),
        b.get("client_secret", ""),
        b.get("redirect_uri", "")
    )
    return jsonify({"ok": True, "configured": gdrive_manager.is_configured()})

@app.get("/api/gdrive/auth")
@auth.require_auth
def gdrive_auth():
    if not gdrive_manager.is_configured():
        return jsonify({"error": "Google OAuth not configured"}), 400
    return jsonify({"url": gdrive_manager.get_auth_url()})

@app.get("/api/gdrive/callback")
def gdrive_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return "Missing code", 400
    try:
        gdrive_manager.handle_callback(code, state)
        return redirect("/#gdrive-connected")
    except Exception as e:
        return f"OAuth error: {e}", 500

@app.delete("/api/gdrive/revoke")
@auth.require_auth
def gdrive_revoke():
    gdrive_manager.revoke()
    return jsonify({"ok": True})

@app.get("/api/gdrive/files")
@auth.require_auth
def gdrive_files():
    folder_id = request.args.get("folder", "root")
    try:
        return jsonify(gdrive_manager.list_files(folder_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/gdrive/download/<file_id>")
@auth.require_auth
def gdrive_download(file_id):
    try:
        data, filename, mime = gdrive_manager.download_file(file_id)
        return send_file(io.BytesIO(data), download_name=filename,
                         as_attachment=True, mimetype=mime or "application/octet-stream")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/gdrive/upload")
@auth.require_auth
def gdrive_upload():
    folder_id = request.args.get("folder","root")
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400
    try:
        gdrive_manager.upload_file(folder_id, f.filename, f.read(),
                                   f.content_type or "application/octet-stream")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.delete("/api/gdrive/delete/<file_id>")
@auth.require_auth
def gdrive_delete(file_id):
    try:
        gdrive_manager.delete_file(file_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/gdrive/mkdir")
@auth.require_auth
def gdrive_mkdir():
    b = request.get_json(force=True) or {}
    try:
        fid = gdrive_manager.create_folder(b.get("parent","root"), b.get("name","New Folder"))
        return jsonify({"id": fid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── SMB Proxy Credentials ─────────────────────────────────────────────────────
@app.get("/api/smb/proxy-credentials")
@auth.require_auth
def get_smb_proxy_creds():
    creds_file = Path(os.environ.get("DATA_DIR", "/app/data")) / "smb_proxy_credentials.json"
    if creds_file.exists():
        d = json.loads(creds_file.read_text())
        return jsonify({"username": d.get("username", "sagedrive"), "configured": True})
    return jsonify({"username": "sagedrive", "configured": False})

@app.post("/api/smb/proxy-credentials")
@auth.require_auth
def set_smb_proxy_creds():
    body = request.get_json(force=True) or {}
    username = (body.get("username") or "sagedrive").strip()
    password = (body.get("password") or "").strip()
    if not password:
        return jsonify({"error": "Password is required"}), 400
    creds_file = Path(os.environ.get("DATA_DIR", "/app/data")) / "smb_proxy_credentials.json"
    creds_file.write_text(json.dumps({"username": username, "password": password}, indent=2))
    # Apply immediately — update the running smbd without full restart
    import subprocess
    try:
        subprocess.run(["groupadd", "-f", "sambausers"], check=False)
        subprocess.run(["useradd", "-M", "-s", "/sbin/nologin", "-G", "sambausers", username],
                       check=False, capture_output=True)
        subprocess.run(["usermod", "-aG", "sambausers", username], check=False, capture_output=True)
        proc = subprocess.run(
            ["smbpasswd", "-s", "-a", username],
            input=f"{password}\n{password}\n",
            text=True, capture_output=True
        )
        return jsonify({"ok": True, "message": f"Credentials saved. Reconnect as '{username}'."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
