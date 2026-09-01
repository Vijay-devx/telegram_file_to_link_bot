# Telegram File-to-Link Proxy Bot

A high-performance, diskless proxy bot that bridges Telegram MTProto and standard HTTP. It allows you to generate direct download links for Telegram files without caching the files on disk, fully supporting HTTP Range requests.

## Deployment Playbook: Render (Native Python)

Render supports native Python deployments via a `start.sh` script and does not block outbound TCP ports, making it a perfect free alternative for our MTProto architecture.

### 1. Repository Setup
Push this entire project to a private GitHub repository.

### 2. Render Setup
1. Log in to Render ([render.com](https://render.com/)).
2. Click **New** -> **Web Service**.
3. Connect your GitHub account and select your private repository.
4. **Name:** `telegram-file-proxy` (or whatever you prefer).
5. **Environment:** Select `Python`.
6. **Build Command:** `pip install -r requirements.txt`
7. **Start Command:** `bash start.sh`
8. **Instance Type:** Select the **Free** tier.

### 3. Environment Variables
Scroll down to the **Environment Variables** section and click **Add Environment Variable**. Add your variables:
- `BOT_TOKEN`: Your BotFather Token
- `API_ID`: Your Telegram API ID
- `API_HASH`: Your Telegram API Hash
- `LINK_TTL_HOURS`: `3`

*Note on BASE_URL:* Do NOT set `BASE_URL` (or `DOMAIN`) yet. Render will generate a URL for you (e.g., `https://your-app.onrender.com`). Once deployed, copy that URL, add it as the `BASE_URL` environment variable, and Render will restart the app so the bot replies with correct links. Click **Create Web Service**.

### 4. The Free Tier "Sleep" Disclaimer
**IMPORTANT:** Render's free tier spins down the web service after 15 minutes of inactivity. 

*What this means:* If you forward a file to the bot while it is asleep, it will not reply immediately. You must "wake it up" by loading your Render URL (`https://your-app.onrender.com`) in a web browser. Once the page loads (waking the server), the bot will process the forwarded message and reply with your download link.
