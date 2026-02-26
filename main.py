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

def get_po_token(proxy: Optional[str] = None):
    """Generate visitorData and poToken using youtube-po-token-generator"""
    env = os.environ.copy()
    # Limit memory usage for Node.js to stay within small Koyeb instance limits (e.g. 512MB for Micro)
    # jsdom is memory intensive; 320MB is a safer limit for Micro instances.
    env["NODE_OPTIONS"] = "--max-old-space-size=320"
    if proxy:
        # The PO token generator uses `global-agent` which ONLY supports HTTP proxies, not SOCKS5.
        # So we route it to the specific HTTP proxy port we opened in wireproxy (8080).
        env["HTTPS_PROXY"] = "http://127.0.0.1:8080"
        env["HTTP_PROXY"] = "http://127.0.0.1:8080"
    
    logger.info("Generating PO token...")
    try:
        # Assuming the npm package is installed globally
        result = subprocess.run(
            ["youtube-po-token-generator"], 
            env=env,
            capture_output=True, 
            text=True, 
            check=True
        )
        data = json.loads(result.stdout)
        return data.get("visitorData"), data.get("poToken")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate PO token: {e.stderr}")
        return None, None
    except Exception as e:
        logger.error(f"Exception generating PO token: {e}")
        return None, None

@app.post("/extract")
async def extract_info(req: ExtractRequest):
    """Extract metadata using yt-dlp with WARP, PO Tokens, and Cookies"""
    
    # Base command (Running through python module to avoid PATH issues on Windows local)
    cmd = ["python", "-m", "yt_dlp", "--dump-json", "--no-warnings", req.url]

    # 1. WARP Proxy (or Custom Proxy)
    # Default to the local wireproxy WARP tunnel
    active_proxy = req.proxy or os.environ.get("USE_PROXY") or "socks5://127.0.0.1:1080"
    if active_proxy:
        cmd.extend(["--proxy", active_proxy])

    # 2. Cookies
    if COOKIES_FILE:
        cmd.extend(["--cookies", COOKIES_FILE])

    # 3. PO Tokens
    visitor_data, po_token = get_po_token(active_proxy)
    if visitor_data and po_token:
        # Pass tokens to yt-dlp via extractor args
        ext_args = f"youtube:visitor_data={visitor_data};po_token={po_token};player_client=android,mweb"
        cmd.extend(["--extractor-args", ext_args])
        logger.info("Injected PO token and customized player client.")
    else:
        logger.warning("Failed to generate PO token. Proceeding without it...")
        # Still apply client impersonation as fallback
        cmd.extend(["--extractor-args", "youtube:player_client=android,mweb"])

    # 4. User-Agent
    # If using cookies, the User-Agent should ideally match the one used to export them.
    ua = os.environ.get("USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    cmd.extend(["--user-agent", ua])

    logger.info(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"yt-dlp error: {result.stderr}")
            raise HTTPException(status_code=400, detail=result.stderr)
        
        info = json.loads(result.stdout)
        return info
    except Exception as e:
        logger.error(f"Execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}
