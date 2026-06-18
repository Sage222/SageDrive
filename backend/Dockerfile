FROM python:3.12-slim

# Install existing dependencies + Samba, Rclone, and FUSE
RUN apt-get update && apt-get install -y --no-install-recommends \
    smbclient \
    libsmbclient-dev \
    gcc \
    samba \
    rclone \
    fuse3 \
    && rm -rf /var/lib/apt/lists/*

# Fix FUSE permissions
RUN sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf

WORKDIR /app
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .

# Move Samba config
RUN cp smb.conf /etc/samba/smb.conf

EXPOSE 8080 445

ENTRYPOINT ["/app/entrypoint.sh"]
