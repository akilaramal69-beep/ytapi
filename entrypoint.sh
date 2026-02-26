#!/bin/bash
set -e

echo "Starting YouTube Downloader API startup sequence..."

# 1. Generate Cloudflare WARP config using wgcf
if [ ! -f "wgcf-profile.conf" ]; then
    echo "Registering WARP account..."
    yes | wgcf register --accept-tos
    echo "Generating WARP config..."
    wgcf generate
    
    # Append the Socks5 config specifically for wireproxy
    echo "" >> wgcf-profile.conf
    echo "[Socks5]" >> wgcf-profile.conf
    echo "BindAddress = 127.0.0.1:1080" >> wgcf-profile.conf
    
    echo "WARP config generated."
else
    echo "WARP config already exists."
fi

# 2. Start wireproxy in the background
echo "Starting wireproxy SOCKS5 server on port 1080..."
wireproxy -c wgcf-profile.conf &
PROXY_PID=$!

# Give it a few seconds to establish connection
sleep 3

# 3. Start the FastAPI server using Uvicorn
export PORT=${PORT:-8000}
echo "Starting Uvicorn FastAPI server on port $PORT..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT

# Note: For production use, wireproxy run as a background task. 
# If it crashes, uvicorn will still run but the proxy won't function.
# You could use a tool like supervisord if you want better process management.
