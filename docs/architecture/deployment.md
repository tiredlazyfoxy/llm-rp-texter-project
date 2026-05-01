# Deployment

## Docker Architecture

Two compose files, two custom Docker images:

| File | Purpose |
|------|---------|
| `docker-compose.dev.yml` | Local development (source mounts, hot-reload) |
| `docker-compose.prod.yml` | Production (pre-built images from NAS) |

## Production Services

### gate (nginx)

- Image: `iezious/llmrp-gate:latest`
- Multi-stage Dockerfile: `frontend/Dockerfile` (Node build → nginx:alpine)
- Serves all three SPAs as static files
- Proxies `/api` to backend with SSE support (no buffering, 300s timeout)
- Config: `nginx/prod.conf`

### backend (FastAPI)

- Image: `iezious/llmrp-api:latest`
- Dockerfile: `backend/Dockerfile` (python:3.13)
- Runs uvicorn on port 8085
- SQLite DB at `/app/data/llmrp.db` (volume-mounted)
- Health check: `GET /api/health`

## URL Routing (Production)

| Path | Target |
|------|--------|
| `/` | User SPA (static) |
| `/admin` | Admin SPA (static) |
| `/login` | Login SPA (static) |
| `/api/*` | FastAPI backend (proxied) |

## nginx Production Config

Located at `nginx/prod.conf`, key features:

- SSE streaming: `proxy_buffering off`, `proxy_cache off`
- Long timeout: `proxy_read_timeout 300s` (LLM generation)
- Multi-SPA fallback: each SPA path falls back to its own `index.html`
- No CORS needed (same-origin via proxy)

## Build and Distribution

Images are built locally, compressed with 7z, and stored on a NAS share. No Docker registry used.

### Prerequisites

- Git tag for versioning: `git tag v0.0.1`
- `DOCKER_STORE` environment variable pointing to NAS mount
- Docker and 7z installed

### build.ps1 (Windows — build machine)

```powershell
.\build.ps1              # Build images + copy compose (default)
.\build.ps1 -Images      # Build and compress images only
.\build.ps1 -Config      # Copy docker-compose.prod.yml only
```

Steps:
1. Reads version from `git describe --tags --abbrev=0`
2. Builds `iezious/llmrp-api:$version` + `:latest`
3. Builds `iezious/llmrp-gate:$version` + `:latest`
4. `docker save` → 7z compress → move to `$DOCKER_STORE/llmrp/`
5. Copies `docker-compose.prod.yml` as `docker-compose.yml`

### fetch.sh (Linux — deployment server)

```bash
./fetch.sh               # Load images + copy compose (default)
./fetch.sh --images      # Load images only
./fetch.sh --config      # Copy compose only
```

Steps:
1. Reads 7z archives from `$DOCKER_STORE/llmrp/`
2. `7z x -so | docker load` for each image
3. Copies `docker-compose.yml` to working directory

### Deployment

```bash
# On the server, after fetch:
docker compose up -d
```

Environment variables via `.env` file (not checked into git):
- `OPENAI_API_KEY`, `LLAMA_SWAP_URL` — LLM provider config
- `SEARCH_CSE_ID`, `SEARCH_CSE_KEY` — Google search (optional)

## Files

| File | Purpose |
|------|---------|
| `backend/Dockerfile` | Backend image (python:3.13, uvicorn) |
| `frontend/Dockerfile` | Frontend image (node build → nginx) |
| `nginx/prod.conf` | Production nginx config (SSE, multi-SPA) |
| `nginx/dev.conf` | Dev nginx config (proxy to Vite + backend) |
| `docker-compose.prod.yml` | Production compose (pre-built images) |
| `docker-compose.dev.yml` | Dev compose (source mounts, hot-reload) |
| `build.ps1` | Build + compress + export to NAS |
| `fetch.sh` | Import from NAS + deploy |
| `.dockerignore` | Excludes .git, .venv, node_modules, docs |
