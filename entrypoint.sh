#!/bin/bash
set -e

echo "=== SageDrive Startup ==="

# A) Generate Rclone config from SageDrive's gdrive_token.json
# gdrive_manager.py stores client_id, client_secret AND tokens all in one file
python3 << 'PYEOF'
import json, os
from pathlib import Path

token_file = Path('/app/data/gdrive_token.json')
try:
    d = json.loads(token_file.read_text())
    rclone_token = json.dumps({
        "access_token": d.get("token", ""),
        "token_type": "Bearer",
        "refresh_token": d.get("refresh_token", ""),
        "expiry": "2020-01-01T00:00:00Z"
    })
    conf = f"""[gdrive]
type = drive
client_id = {d.get("client_id", "")}
client_secret = {d.get("client_secret", "")}
scope = drive
token = {rclone_token}
"""
    os.makedirs('/root/.config/rclone', exist_ok=True)
    with open('/root/.config/rclone/rclone.conf', 'w') as f:
        f.write(conf)
    print("✅ Rclone config written successfully!")
    print(f"   client_id present: {bool(d.get('client_id'))}")
    print(f"   refresh_token present: {bool(d.get('refresh_token'))}")
except FileNotFoundError:
    print("⚠️  gdrive_token.json not found — Google Drive not yet authenticated.")
except Exception as e:
    print(f"❌ Failed to write rclone config: {e}")
PYEOF

# B) Mount Google Drive via FUSE
mkdir -p /mnt/gdrive
if grep -q "refresh_token" /root/.config/rclone/rclone.conf 2>/dev/null; then
    echo "Mounting Google Drive..."
    rclone mount gdrive: /mnt/gdrive \
        --allow-other \
        --vfs-cache-mode writes \
        --vfs-cache-max-size 512M \
        --dir-cache-time 5m \
        --log-level INFO \
        --daemon
    sleep 2
    echo "✅ Google Drive mounted at /mnt/gdrive"
    ls /mnt/gdrive | head -5 || echo "(empty or mounting...)"
else
    echo "⚠️  Skipping mount — no valid rclone config."
fi

# C) Start Samba (foreground in background — correct Docker approach)
echo "Starting Samba..."
smbd --foreground --no-process-group &
nmbd --foreground --no-process-group &
echo "✅ Samba started"

# D) Start SageDrive Flask app
echo "Starting SageDrive web interface on :8080..."
cd /app
exec python3 main.py
