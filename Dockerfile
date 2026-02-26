FROM python:3.11-slim

# Install system dependencies:
# - ffmpeg (for video/audio stitching)
# - curl, inetutils-ping, ca-certificates (general networking tasks)
# - nodejs & npm (for youtube-po-token-generator)
# - wireguard-tools, iproute2, resolvconf (for WARP / wgcf if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    nodejs \
    npm \
    wget \
    wireguard-tools \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Install wgcf (WARP config generator)
RUN wget -O /usr/local/bin/wgcf https://github.com/ViRb3/wgcf/releases/download/v2.2.22/wgcf_2.2.22_linux_amd64 \
    && chmod +x /usr/local/bin/wgcf

# Install wireproxy (WARP SOCKS5 client)
RUN wget -O /tmp/wireproxy.tar.gz https://github.com/pufferffish/wireproxy/releases/download/v1.0.8/wireproxy_linux_amd64.tar.gz \
    && tar -xzf /tmp/wireproxy.tar.gz -C /usr/local/bin/ \
    && rm /tmp/wireproxy.tar.gz

# Install youtube-po-token-generator globally
RUN npm install -g youtube-po-token-generator

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh

# Expose the API port
ENV PORT=8000
EXPOSE 8000

# Specify Koyeb's HEALTHCHECK equivalent if needed
HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl -f http://localhost:${PORT}/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
