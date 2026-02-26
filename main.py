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
    try:
        cookies_decoded = base64.b64decode(os.environ["YOUTUBE_COOKIES"]).decode("utf-8")
        fd, COOKIES_FILE = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(cookies_decoded)
        logger.info("Loaded YouTube cookies from environment variables.")
    except Exception as e:
        logger.error(f"Failed to decode YOUTUBE_COOKIES: {e}")

class ExtractRequest(BaseModel):
    url: str
    proxy: Optional[str] = None

def get_po_token(proxy: Optional[str] = None):
    """Generate visitorData and poToken using youtube-po-token-generator"""
    env = os.environ.copy()
    if proxy:
        env["HTTPS_PROXY"] = proxy
        env["HTTP_PROXY"] = proxy
    
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
    # Since we are testing locally without wireproxy right now, we will default to None if not provided
    active_proxy = req.proxy or os.environ.get("USE_PROXY") 
    if active_proxy:
        cmd.extend(["--proxy", active_proxy])

    # 2. Cookies
    if COOKIES_FILE:
        cmd.extend(["--cookies", COOKIES_FILE])

    # 3. PO Tokens
    visitor_data, po_token = get_po_token(active_proxy)
    if visitor_data and po_token:
        # Pass tokens to yt-dlp via extractor args
        ext_args = f"youtube:visitor_data={visitor_data};po_token={po_token};player_client=ios,tv"
        cmd.extend(["--extractor-args", ext_args])
        logger.info("Injected PO token and customized player client.")
    else:
        logger.warning("Failed to generate PO token. Proceeding without it...")
        # Still apply client impersonation as fallback
        cmd.extend(["--extractor-args", "youtube:player_client=ios,tv"])

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
