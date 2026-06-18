FROM python:3.11-slim

# Install Samba, Rclone, and FUSE
RUN apt-get update && \
    apt-get install -y samba rclone fuse3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Fix FUSE permissions in Docker
RUN sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy our custom Samba config
RUN cp smb.conf /etc/samba/smb.conf

EXPOSE 8080 445

ENTRYPOINT ["/app/entrypoint.sh"]
