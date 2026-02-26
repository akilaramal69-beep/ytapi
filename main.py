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
    active_proxy = req.proxy or os.environ.get("USE_PROXY") or "socks5://127.0.0.1:1080"
    ua = os.environ.get("USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def run_ytdlp(force_web=False, verbose=False):
        cmd = ["python", "-m", "yt_dlp", "--dump-json", req.url]
        if verbose:
            cmd.append("--verbose")
        else:
            cmd.append("--no-warnings")
            
        if active_proxy:
            cmd.extend(["--proxy", active_proxy])
        if COOKIES_FILE:
            cmd.extend(["--cookies", COOKIES_FILE])
        cmd.extend(["--user-agent", ua])
        
        # Extractor args
        # 1. Player client spoofing
        client = "web" if force_web else "android,mweb"
        
        # 2. Explicitly point to the local BgUtils POT provider server
        # Even though it's supposed to be automatic, being explicit is safer
        ext_args = f"youtube:player_client={client};youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416"
        
        cmd.extend(["--extractor-args", ext_args])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True)

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
