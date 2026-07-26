# VividWrite Deployment

This guide deploys VividWrite on one Ubuntu server with Docker Compose. The
frontend is served by Nginx, and Nginx proxies `/api`, `/charts`, `/uploads`,
and `/health` to the FastAPI backend.

## Server Requirements

- Ubuntu 22.04 or newer is recommended.
- At least 8 GB RAM is recommended because the backend loads Torch,
  Transformers, and Google DePlot.
- At least 30 GB free disk is recommended. The Docker image and DePlot model
  cache are large.
- Outbound network access is required for DeepSeek, Alibaba Cloud DashScope,
  and the first DePlot model download from Hugging Face.

## 1. Install Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker
```

Confirm Docker Compose is available:

```bash
docker compose version
```

On a 4 GB RAM server, add swap before building the backend image:

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. Put the Code on the Server

If the project is in a Git repository:

```bash
git clone <your-repository-url> VividWrite
cd VividWrite
```

If it is only on your local machine, upload the folder to the server, excluding
`backend/venv`, `frontend/node_modules`, generated images, and `.env` files.

## 3. Configure Environment Variables

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Fill in at least:

```bash
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
```

Use `deepseek-v4-flash` first to control cost. Switch to
`deepseek-v4-pro` if chart alignment or revision feedback quality is not good
enough.

For map/process visual feedback and spatial sample essays, also configure:

```bash
WAN_API_KEY=...
WAN_WORKSPACE_ID=...
ALIBABA_MODEL_STUDIO_REGION=cn-beijing
WAN_IMAGE_MODEL=wan2.7-image
QWEN_VL_MODEL=qwen3.7-plus
```

For an overseas server, Alibaba Cloud International in Singapore is usually the
cleanest region choice. Create the Model Studio key and workspace in the same
region, then use:

```bash
ALIBABA_MODEL_STUDIO_REGION=ap-southeast-1
WAN_WORKSPACE_ID=ws-your-singapore-workspace
```

Do not mix a Beijing API key with a Singapore endpoint, or the reverse.

For a shared research-test deployment, enable the built-in login:

```bash
APP_AUTH_ENABLED=true
APP_TEST_USERS=tester01,tester02,tester03,tester04,tester05
APP_SHARED_PASSWORD_HASH=<generated PBKDF2 hash>
APP_SESSION_SECRET=<random 64-character value>
APP_SESSION_TTL_SECONDS=43200
APP_COOKIE_SECURE=false
```

Use `deploy/configure_auth.py` to generate the password hash and session secret
without putting the shared plaintext password in source code. Set
`APP_COOKIE_SECURE=true` after HTTPS is enabled.

Do not commit `backend/.env`.

## 4. Build and Start

```bash
docker compose up -d --build
```

Check status:

```bash
docker compose ps
docker compose logs -f backend
```

The first statistical chart request can be slow because the backend downloads
and caches `google/deplot`. The cache is stored in the `model_cache` Docker
volume, so later restarts should not download it again.

## 5. Test

From the server:

```bash
curl http://127.0.0.1/health
```

From your browser:

```text
http://<server-ip>/
```

Then upload a test chart, sign in with a configured test account, generate a sample essay,
advance to Revision, and click Analyze Text.

## 6. Domain and HTTPS

Point your domain's DNS `A` record to the server IP. After DNS resolves, either:

- Put this Compose stack behind an existing HTTPS reverse proxy, or
- Install Certbot/Nginx on the host and proxy HTTPS traffic to `127.0.0.1:80`.

If you run another web server on the host, change the `web` port mapping in
`docker-compose.yml`, for example:

```yaml
ports:
  - "127.0.0.1:8080:80"
```

Then let the host reverse proxy forward your domain to `http://127.0.0.1:8080`.

## Low-Cost Server Choice

For a personal research prototype, start with an Asia-region 4 GB RAM VPS and
upgrade only if DePlot requests are slow or the backend is killed by the OOM
killer.

Recommended starting point:

```text
2 vCPU / 4 GB RAM / 60-80 GB SSD, Singapore or Tokyo
```

More comfortable demo server:

```text
2-4 vCPU / 8 GB RAM / 80-160 GB SSD, Singapore or Tokyo
```

Without a domain, the app can run on:

```text
http://<server-ip>/
```

This avoids domain and CDN cost during development. Add a domain and HTTPS only
when you need to share the system with external evaluators.

As of 25 July 2026, the useful budget reference points are:

- DigitalOcean Basic Droplet: 4 GB / 2 vCPU / 80 GB is about USD 24/month;
  8 GB / 4 vCPU / 160 GB is about USD 48/month.
- AWS Lightsail Linux with public IPv4: 4 GB / 2 vCPU / 80 GB is about
  USD 24/month; 8 GB / 2 vCPU / 160 GB is about USD 44/month.
- Hetzner is cheaper in Europe, but domestic China routing is usually less
  predictable than Singapore or Tokyo for an interactive writing tool.

API cost controls:

- Use `DEEPSEEK_MODEL=deepseek-v4-flash` while developing.
- Use `WAN_IMAGE_MODEL=wan2.7-image` instead of `wan2.7-image-pro` until the
  map/process feedback quality justifies the higher price.
- Keep map/process visual feedback as an explicit Revision action. Do not
  generate Wan images automatically on every keystroke.

## Common Operations

Restart:

```bash
docker compose restart
```

Stop:

```bash
docker compose down
```

Update after pulling code:

```bash
git pull
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f backend
docker compose logs -f web
```

Back up user data:

```bash
docker run --rm -v vividwrite_backend_user_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/vividwrite-user-data.tgz -C /data .
```

## Notes

- The frontend Docker build uses `VITE_API_BASE=""`, so browser requests go to
  same-origin paths such as `/api/analyze-chart-with-image`.
- The backend runtime directories are Docker volumes:
  `backend_uploads`, `backend_charts`, `backend_user_data`, and `model_cache`.
- If the server cannot reach Hugging Face, pre-download or mirror the
  `google/deplot` model before first use.
