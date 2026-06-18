#!/bin/bash

# A) Translate SageDrive's OAuth tokens to Rclone config
python3 -c "
import json, os
try:
    t = json.loads(open('/app/data/gdrive_token.json').read())
    c = json.loads(open('/app/data/gdrive_client.json').read())
    rclone_token = {
        'access_token': t.get('token', ''),
        'token_type': 'Bearer',
        'refresh_token': t.get('refresh_token', ''),
        'expiry': '2020-01-01T00:00:00Z' # Force refresh immediately
    }
    conf = f\"\"\"[gdrive]
type = drive
client_id = {c.get('client_id')}
client_secret = {c.get('client_secret')}
scope = drive
token = {json.dumps(rclone_token)}
\"\"\"
    os.makedirs('/root/.config/rclone', exist_ok=True)
    with open('/root/.config/rclone/rclone.conf', 'w') as f:
        f.write(conf)
    print('✅ Rclone config generated from SageDrive tokens!')
except Exception as e:
    print('⚠️ Could not generate Rclone config (Google Drive might not be linked yet).')
"

# B) Mount Google Drive (if config exists)
mkdir -p /mnt/gdrive
if [ -f /root/.config/rclone/rclone.conf ]; then
    echo "Mounting Google Drive via FUSE..."
    # --daemon puts it in the background, --allow-other lets Samba read it
    rclone mount gdrive: /mnt/gdrive --daemon --allow-other --vfs-cache-mode writes
fi

# C) Start Samba Daemon
echo "Starting SMB Server..."
smbd -D

# D) Start the original SageDrive Python backend
echo "Starting SageDrive Web Interface..."
exec python3 main.py
