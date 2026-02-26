# YouTube Downloader API (WARP + PO Token Strategy)

This project is a FastAPI-based server that acts as a robust metadata extractor wrapper around `yt-dlp`. It is specifically engineered to bypass YouTube's datacenter IP restrictions (such as those encountered on cloud providers like Koyeb, Heroku, or standard VPS servers).

It achieves this using a multi-layered bypass approach:
1. **Cloudflare WARP (`wireproxy`)**: Automatically routes all requests through a residential Cloudflare edge node (SOCKS5), dodging datacenter IP blocks.
2. **BgUtils POT Provider**: Integrates the `bgutil-ytdlp-pot-provider` plugin and a local HTTP server (port 4416) to automatically generate and inject high-quality PO tokens.
3. **Cookie Injection**: Optionally accepts a Netscape `cookies.txt` file (raw text) for handling age-gated or heavily flagged videos.
4. **Client Synchronization**: Automatically alternates between **Web** and **Android** clients, ensuring PO tokens are correctly validated by the respective playback protocols.

## Architecture & Boot Sequence
- The application uses a single **Dockerfile**.
- On boot, `entrypoint.sh` registers an anonymous Cloudflare WARP tunnel and starts `wireproxy`.
- A background **BgUtils POT Provider** server is launched on port 4416, routed through the WARP proxy to ensure IP synchronization.
- The `uvicorn` web server starts the FastAPI application.
- The `bgutil-ytdlp-pot-provider` plugin for `yt-dlp` handles the automated handshake for visitor data and tokens.

## Deployment to Koyeb

This API is designed to be 1-click deployable to Koyeb using Docker.

1. Fork or clone this repository to your GitHub account.
2. Go to the Koyeb Dashboard and click **Create App**.
3. Select **GitHub** and choose your repository.
4. **Builder Configuration:**
   - Choose the **Dockerfile** build method.
   - Leave the `Run Command` blank (the Dockerfile entrypoint handles it automatically).
5. **Environment Variables (Optional):**
   - `PORT`: Default is `8000`.
   - `YOUTUBE_COOKIES`: The **raw text** (Netscape format) of your `cookies.txt` file.
   - `USER_AGENT`: Optional. If using cookies, set this to match the browser used to export them.
   - `USE_PROXY`: Overrides the built-in Cloudflare WARP proxy.
6. **Instance Size:** A **Micro** (512MB) instance or higher is recommended. While the new provider is more efficient, running Node.js, Wireguard, and FFmpeg concurrently requires decent headroom.
7. Set the Exposed Port to match the `PORT` (e.g. `8000`).

## API Usage

The API exposes a single main endpoint for metadata extraction.

**`POST /extract`**

Extracts raw `yt-dlp` JSON outputs for a given video URL.

```bash
curl -X POST https://your-koyeb-app-name.koyeb.app/extract \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

Watch the container logs during the request to verify the Cloudflare proxy and PO-tokens are being utilized successfully.
