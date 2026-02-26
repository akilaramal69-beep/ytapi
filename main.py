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
    """Extract metadata using yt-dlp with WARP, optional PO Tokens, and Cookies"""
    
    # Base command logic
    active_proxy = req.proxy or os.environ.get("USE_PROXY") or "socks5://127.0.0.1:1080"
    ua = os.environ.get("USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def run_ytdlp(visitor_data=None, po_token=None):
        cmd = ["python", "-m", "yt_dlp", "--dump-json", "--no-warnings", req.url]
        if active_proxy:
            cmd.extend(["--proxy", active_proxy])
        if COOKIES_FILE:
            cmd.extend(["--cookies", COOKIES_FILE])
        cmd.extend(["--user-agent", ua])
        
        # Extractor args for client spoofing and optional tokens
        ext_args = "youtube:player_client=android,mweb"
        if visitor_data and po_token:
            ext_args += f";visitor_data={visitor_data};po_token={po_token}"
        
        cmd.extend(["--extractor-args", ext_args])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True)

    # Attempt 1: Without PO Tokens (Faster/Lighter)
    result = run_ytdlp()
    
    # Check if we got the "bot" block error
    if result.returncode != 0 and "Sign in to confirm you’re not a bot" in result.stderr:
        logger.warning("Simple extraction blocked by bot detection. Attempting with PO Tokens fallback...")
        
        # Attempt 2: Generate PO tokens and retry
        visitor_data, po_token = get_po_token(active_proxy)
        if visitor_data and po_token:
            result = run_ytdlp(visitor_data, po_token)
        else:
            logger.error("Failed to generate fallback PO tokens.")
            # We still proceed to return the original error if fallback generation failed

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
