import os
import json
import logging
import subprocess
import tempfile
import base64
import shutil
import yt_dlp
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

# 1. Force the PATH in the current process memory so yt-dlp finds Node.js
node_path = shutil.which("node")
if node_path:
    os.environ["PATH"] = f"{os.path.dirname(node_path)}:{os.environ.get('PATH', '')}"
    logger.info(f"Forced exact Node.js path into current process memory: {os.environ['PATH']}")

@app.post("/extract")
async def extract_info(req: ExtractRequest):
    """Extract metadata using yt-dlp with WARP, automatic PO Tokens via BgUtils, and Cookies"""
    logger.info("Starting native yt-dlp extraction...")
    
    # Use socks5h for remote DNS resolution via WARP
    active_proxy = req.proxy or os.environ.get("USE_PROXY") or "socks5h://127.0.0.1:1080"
    ua = os.environ.get("USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # Define the arguments for yt_dlp object
    ydl_opts = {
        'dumpjson': True,
        'proxy': active_proxy,
        'http_headers': {'User-Agent': ua},
        'verbose': True,
        'no_warnings': False,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web']
            },
            'youtubepot-bgutilhttp': {
                'base_url': ['http://127.0.0.1:4416']
            }
        }
    }
    
    if COOKIES_FILE:
        ydl_opts['cookiefile'] = COOKIES_FILE

    # Execute directly in Python (No subprocesses!)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info with download=False extracts metadata
            info = ydl.extract_info(req.url, download=False)
            return info
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp native extraction failed: {e}")
        # Could try falling back to without proxy or different client, but for now just raise
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}
