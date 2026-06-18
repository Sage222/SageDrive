"""gdrive_manager.py – Google Drive OAuth2 flow + file operations."""
import json, os, io
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
CREDS_FILE = DATA_DIR / "gdrive_token.json"

CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI  = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8080/api/gdrive/callback")
SCOPES        = ["https://www.googleapis.com/auth/drive"]

_pending_state = None


def is_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


def is_authenticated() -> bool:
    if not CREDS_FILE.exists():
        return False
    creds = _load_creds()
    return creds is not None and (creds.valid or bool(creds.refresh_token))


def _load_creds():
    if not CREDS_FILE.exists():
        return None
    data = json.loads(CREDS_FILE.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id", CLIENT_ID),
        client_secret=data.get("client_secret", CLIENT_SECRET),
        scopes=data.get("scopes", SCOPES),
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds)
    return creds if creds.valid else None


def _save_creds(creds: Credentials):
    CREDS_FILE.write_text(json.dumps({
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes or SCOPES),
    }))


def _service():
    creds = _load_creds()
    if not creds:
        raise RuntimeError("Not authenticated with Google Drive")
    return build("drive", "v3", credentials=creds)


def get_auth_url() -> str:
    global _pending_state
    flow = Flow.from_client_config(
        {"web": {
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
        }},
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _pending_state = state
    return auth_url


def handle_callback(code: str, state: str) -> bool:
    global _pending_state
    flow = Flow.from_client_config(
        {"web": {
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
        }},
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state,
    )
    flow.fetch_token(code=code)
    _save_creds(flow.credentials)
    _pending_state = None
    return True


def revoke():
    CREDS_FILE.unlink(missing_ok=True)


def list_files(folder_id: str = "root") -> list:
    svc = _service()
    results = svc.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id,name,mimeType,size,modifiedTime,parents)",
        pageSize=200,
    ).execute()
    files = []
    for f in results.get("files", []):
        is_folder = f["mimeType"] == "application/vnd.google-apps.folder"
        files.append({
            "id":       f["id"],
            "name":     f["name"],
            "type":     "folder" if is_folder else "file",
            "size":     int(f.get("size", 0)),
            "modified": f.get("modifiedTime", ""),
            "mimeType": f["mimeType"],
            "parents":  f.get("parents", []),
        })
    return files


def download_file(file_id: str):
    svc  = _service()
    meta = svc.files().get(fileId=file_id, fields="name,mimeType").execute()
    name = meta["name"]
    mime = meta["mimeType"]
    export_map = {
        "application/vnd.google-apps.document":
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.google-apps.spreadsheet":
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.presentation":
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    buf = io.BytesIO()
    if mime in export_map:
        req = svc.files().export_media(fileId=file_id, mimeType=export_map[mime])
    else:
        req = svc.files().get_media(fileId=file_id)
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue(), name, mime


def upload_file(parent_id: str, filename: str, data: bytes, mime_type: str = "application/octet-stream"):
    svc   = _service()
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=True)
    svc.files().create(
        body={"name": filename, "parents": [parent_id]},
        media_body=media, fields="id"
    ).execute()


def delete_file(file_id: str):
    _service().files().delete(fileId=file_id).execute()


def create_folder(parent_id: str, name: str) -> str:
    f = _service().files().create(body={
        "name":     name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  [parent_id],
    }, fields="id").execute()
    return f["id"]
