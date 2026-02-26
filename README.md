# YouTube Downloader API (WARP + PO Token Strategy)

This project is a FastAPI-based server that acts as a robust metadata extractor wrapper around `yt-dlp`. It is specifically engineered to bypass YouTube's datacenter IP restrictions (such as those encountered on cloud providers like Koyeb, Heroku, or standard VPS servers).

It achieves this using a multi-layered bypass approach:
1. **Cloudflare WARP (`wireproxy`)**: Automatically routes all requests through a residential Cloudflare edge node (SOCKS5), dodging datacenter IP blocks.
2. **Dynamic PO Tokens (`youtube-po-token-generator`)**: Automatically generates and injects valid `visitorData` and `poToken` tokens for verification.
3. **Cookie Injection**: Optionally accepts a Netscape `cookies.txt` file via Base64 environment variables for handling age-gated or heavily flagged videos.
4. **Client Impersonation**: Spoofs active TV/iOS clients (`player_client=ios,tv`) utilizing `yt-dlp`'s built-in extractor arguments.

## Architecture & Boot Sequence
- The application uses a single **Dockerfile**.
- On boot, `entrypoint.sh` automatically registers an anonymous Cloudflare WARP tunnel using `wgcf`.
- `wireproxy` runs in the background, mapping the WARP connection to a local `socks5://127.0.0.1:1080` server.
- The `uvicorn` web server starts the FastAPI application, binding to `0.0.0.0:${PORT}`.

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
   - `YOUTUBE_COOKIES`: A **Base64** encoded string of your `cookies.txt` file (Netscape format). Bypasses login/age-restriction errors.
   - `USE_PROXY`: Overrides the built-in Cloudflare WARP proxy if you want to use a paid external proxy (e.g., `socks5://user:pass@1.1.1.1:1080`).
6. **Instance Size:** At least `Eco Free` or `Micro` is recommended, as running Node.js (for token generation) and Wireguard uses moderate CPU.
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
