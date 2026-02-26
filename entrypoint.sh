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
    echo "" >> wgcf-profile.conf
    echo "[http]" >> wgcf-profile.conf
    echo "BindAddress = 127.0.0.1:8080" >> wgcf-profile.conf
    
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

# 3. Start BgUtils POT Provider server
echo "Starting BgUtils POT Provider server on port 4416..."
cd /app/bgutil-provider/server
# We use global-agent to force the Node.js process to use the HTTP proxy
export GLOBAL_AGENT_HTTP_PROXY=http://127.0.0.1:8080
export GLOBAL_AGENT_NO_PROXY=127.0.0.1,localhost
# Start with global-agent bootstrap
NODE_OPTIONS="-r global-agent/bootstrap" node build/main.js --port 4416 > /app/provider.log 2>&1 &
POT_PID=$!
cd /app

# Give the provider a moment to initialize
sleep 2

# 4. Start the FastAPI server using Uvicorn
export PORT=${PORT:-8000}
echo "Starting Uvicorn FastAPI server on port $PORT..."
echo "--- Logs from BgUtils Provider (if any) ---"
cat /app/provider.log || true
echo "------------------------------------------"
exec uvicorn main:app --host 0.0.0.0 --port $PORT

# Note: For production use, wireproxy run as a background task. 
# If it crashes, uvicorn will still run but the proxy won't function.
# You could use a tool like supervisord if you want better process management.
