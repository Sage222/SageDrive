#!/bin/bash
set -e

echo "=== SageDrive Startup ==="

# A) Generate Rclone config from SageDrive's gdrive_token.json
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
    sleep 3
    echo "✅ Google Drive mounted at /mnt/gdrive"
else
    echo "⚠️  Skipping mount — no valid rclone config."
fi

# C) Create all directories Samba requires (missing on slim images)
echo "Preparing Samba directories..."
mkdir -p /run/samba
mkdir -p /var/lib/samba/private
mkdir -p /var/cache/samba
mkdir -p /var/log/samba
chmod 755 /run/samba
chmod 700 /var/lib/samba/private

# Ensure the tdb files Samba needs exist
touch /var/lib/samba/account_policy.tdb 2>/dev/null || true

# D) Start Samba
echo "Starting Samba..."
smbd --foreground --no-process-group --log-stdout &
SMBD_PID=$!
sleep 2

# Verify smbd actually bound to port 445
if ss -tlnp | grep -q ':445'; then
    echo "✅ Samba is listening on port 445"
else
    echo "❌ Samba failed to bind port 445 — check logs above"
fi

# E) Start SageDrive Flask app
echo "Starting SageDrive web interface on :8080..."
cd /app
exec python3 main.py
