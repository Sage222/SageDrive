# SageDrive

A self-hosted Docker web file manager providing a unified interface for **SMB/CIFS shares**
and **Google Drive**, secured behind username/password authentication.

## Quick Start

```bash
git clone https://github.com/Sage222/SageDrive && cd SageDrive
cp .env.example .env
# Edit .env — set SECRET_KEY and ADMIN_PASS at minimum
docker compose up -d
```

Open **http://localhost:8080** — log in with `admin` / your `ADMIN_PASS`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `changeme` | Session secret — **always change this** |
| `ADMIN_USER` | `admin` | Initial admin username |
| `ADMIN_PASS` | `changeme` | Initial admin password — **always change this** |
| `SESSION_TTL_HOURS` | `24` | How long sessions last |
| `GOOGLE_CLIENT_ID` | _(empty)_ | Google OAuth2 Client ID |
| `GOOGLE_CLIENT_SECRET` | _(empty)_ | Google OAuth2 Client Secret |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8080/api/gdrive/callback` | Must match your OAuth app |

## Google Drive Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**
2. Create an **OAuth 2.0 Client ID** (type: Web application)
3. Add your redirect URI (e.g. `http://your-server:8080/api/gdrive/callback`) under **Authorised redirect URIs**
4. Copy the Client ID and Secret into your `.env`
5. Restart the container: `docker compose restart`
6. In SageDrive → **Settings** → **Connect Google Drive**

## Features

- 🔐 Bcrypt password auth + Bearer token sessions
- 📁 Multiple SMB/CIFS shares (add any NAS or Windows share)
- ☁️ Google Drive OAuth2 (browse, upload, download, delete, new folder)
- ⬆️ Drag-and-drop file upload
- ⬇️ Authenticated file download
- 🗑️ Delete files and folders
- 📂 Create new folders
- 🌓 Light / dark mode toggle
- 📱 Mobile responsive

## Project Structure

```
SageDrive/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── main.py          # Flask REST API
│   ├── auth.py          # Session auth + bcrypt
│   ├── smb_manager.py   # SMB/CIFS file operations
│   ├── gdrive_manager.py# Google Drive OAuth2 + file ops
│   └── requirements.txt
└── frontend/
    └── public/
        └── index.html   # Single-page app
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/logout` | Logout |
| `GET` | `/api/auth/me` | Current user |
| `GET` | `/api/smb/shares` | List SMB shares |
| `POST` | `/api/smb/shares` | Add SMB share |
| `DELETE` | `/api/smb/shares/:id` | Remove share |
| `GET` | `/api/smb/browse/:id` | Browse share path |
| `GET` | `/api/smb/download/:id` | Download file |
| `POST` | `/api/smb/upload/:id` | Upload file |
| `DELETE` | `/api/smb/delete/:id` | Delete file/folder |
| `POST` | `/api/smb/mkdir/:id` | Create directory |
| `GET` | `/api/gdrive/status` | GDrive connection status |
| `GET` | `/api/gdrive/auth` | Get OAuth URL |
| `GET` | `/api/gdrive/callback` | OAuth callback |
| `DELETE` | `/api/gdrive/revoke` | Disconnect GDrive |
| `GET` | `/api/gdrive/files` | List files in folder |
| `GET` | `/api/gdrive/download/:id` | Download file |
| `POST` | `/api/gdrive/upload` | Upload file |
| `DELETE` | `/api/gdrive/delete/:id` | Delete file |
| `POST` | `/api/gdrive/mkdir` | Create folder |
