import os
import json
import logging
import subprocess
import tempfile
import base64
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="YouTube Downloader API")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load cookies if provided via environment variable
COOKIES_FILE = None
if os.environ.get("YOUTUBE_COOKIES"):
    cookie_val = os.environ["YOUTUBE_COOKIES"]
    try:
        # Try to decode from Base64 first
        try:
            cookies_decoded = base64.b64decode(cookie_val).decode("utf-8")
        except Exception:
            # If decoding fails, assume the user pasted raw Netscape text directly
            cookies_decoded = cookie_val
            
        fd, COOKIES_FILE = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(cookies_decoded)
        logger.info("Loaded YouTube cookies from environment variables successfully.")
    except Exception as e:
        logger.error(f"Failed to process YOUTUBE_COOKIES: {e}")

class ExtractRequest(BaseModel):
    url: str
    proxy: Optional[str] = None

@app.post("/extract")
async def extract_info(req: ExtractRequest):
    """Extract metadata using yt-dlp with WARP, automatic PO Tokens via BgUtils, and Cookies"""
    
    # Base command logic
    # Debug check for Node.js (yt-dlp needs this for JS challenges)
    try:
        node_v = subprocess.check_output(["node", "-v"], text=True).strip()
        logger.info(f"Node.js found: {node_v}")
    except Exception as e:
        logger.error(f"Node.js NOT found in PATH: {e}")
        # Try to find it
        for path in ["/usr/bin/node", "/usr/local/bin/node", "/usr/bin/nodejs"]:
            if os.path.exists(path):
                logger.info(f"Found node at {path}")

    # Use socks5h for remote DNS resolution via WARP
    active_proxy = req.proxy or os.environ.get("USE_PROXY") or "socks5h://127.0.0.1:1080"
    ua = os.environ.get("USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def run_ytdlp(force_web=False, verbose=False):
        cmd = ["python", "-m", "yt_dlp", "--dump-json", req.url]
        if verbose:
            cmd.append("--verbose")
        else:
            cmd.append("--no-warnings")
            
        if COOKIES_FILE:
            cmd.extend(["--cookies", COOKIES_FILE])
        cmd.extend(["--user-agent", ua])
        
        # Extractor args
        client = "web" if force_web else "android,mweb"
        
        # Pass each extractor argument separately to avoid yt-dlp parsing errors combining them
        cmd.extend(["--extractor-args", f"youtube:player_client={client}"])
        cmd.extend(["--extractor-args", "youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416"])
        
        env = os.environ.copy()
        
        # Ensure Node.js directory is explicitly in PATH for yt-dlp's JS runtime check
        current_path = env.get("PATH", "")
        # Prepend standard bin paths so node is found first
        env["PATH"] = f"/usr/bin:/usr/local/bin:{current_path}"
            
        if active_proxy:
            # Explicitly pass the proxy to yt-dlp to prevent IP mismatch leaks
            cmd.extend(["--proxy", active_proxy])
            # Also set env vars just in case other modules need them
            env["ALL_PROXY"] = active_proxy
            env["HTTP_PROXY"] = active_proxy
            env["HTTPS_PROXY"] = active_proxy
            
        env["NO_PROXY"] = "127.0.0.1,localhost"
        
        logger.info(f"Running command: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    # Attempt 1: Standard extraction
    result = run_ytdlp()
    
    # Check if we got a "bot" block error or sign-in requirement
    if result.returncode != 0 and ("Sign in to confirm you’re not a bot" in result.stderr or "403" in result.stderr):
        logger.warning("Extraction blocked or failed. Retrying with 'web' client and verbose logging...")
        # Attempt 2: Force 'web' client and enable verbose for debugging
        result = run_ytdlp(force_web=True, verbose=True)

    # Final result handling
    try:
        if result.returncode != 0:
            logger.error(f"yt-dlp error: {result.stderr}")
            raise HTTPException(status_code=400, detail=result.stderr)
        
        info = json.loads(result.stdout)
        return info
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}
