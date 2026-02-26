#!/bin/bash
set -e

echo "Starting YouTube Downloader API startup sequence..."

# Global OS Hammer: Force Node.js into the absolute global binary directories
echo "Linking Node.js globally for yt-dlp..."
ln -sf $(which node) /usr/bin/node || true
ln -sf $(which node) /usr/local/bin/node || true

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

# Ensure log file exists before tailing
touch /app/provider.log

# Tail the provider log to stdout in the background so it shows up in real-time on Koyeb
tail -f /app/provider.log &
TAIL_PID=$!

cd /app/bgutil-provider/server
# We use both global-agent and standard env vars for proxying
export GLOBAL_AGENT_HTTP_PROXY=http://127.0.0.1:8080
export GLOBAL_AGENT_NO_PROXY=127.0.0.1,localhost
export HTTP_PROXY=http://127.0.0.1:8080
export HTTPS_PROXY=http://127.0.0.1:8080
export NO_PROXY=127.0.0.1,localhost

# Start with global-agent bootstrap and memory limits
NODE_OPTIONS="-r global-agent/bootstrap --max-old-space-size=400" node build/main.js --port 4416 > /app/provider.log 2>&1 &
POT_PID=$!
cd /app

# Give the provider longer to initialize (sometimes takes a bit on nano instances)
sleep 10

# 4. Start the FastAPI server using Uvicorn
export PORT=${PORT:-8000}
echo "Starting Uvicorn FastAPI server on port $PORT..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT

# Note: For production use, wireproxy run as a background task. 
# If it crashes, uvicorn will still run but the proxy won't function.
# You could use a tool like supervisord if you want better process management.
