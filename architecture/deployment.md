# Deployment

## Docker Architecture

Two services, two compose files:

| File | Purpose |
|------|---------|
| `docker-compose.dev.yml` | Local development with build steps |
| `docker-compose.prod.yml` | Production-ready deployment |

## Docker Services

### 1. nginx

- Serves both SPAs as static files (built by Vite)
- User SPA at `/`
- Admin SPA at `/admin`
- Proxies `/api` to the FastAPI backend
- No CORS needed (same-origin)

### 2. FastAPI Backend

- Python 3.13 container
- Runs uvicorn with FastAPI
- Connects to SQLite (volume-mounted)
- Exposes internal port for nginx proxy

## URL Routing (Production)

| Path | Target |
|------|--------|
| `/` | User SPA (static files) |
| `/admin` | Admin SPA (static files) |
| `/api/*` | FastAPI backend (proxied) |

## nginx Configuration Outline

```nginx
server {
    listen 80;

    # User SPA
    location / {
        root /usr/share/nginx/html/user;
        try_files $uri $uri/ /index.html;
    }

    # Admin SPA
    location /admin {
        alias /usr/share/nginx/html/admin;
        try_files $uri $uri/ /admin/index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://backend:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Build Process

1. Frontend: `npm run build` produces static files for both SPAs
2. Backend: Python dependencies installed via `pyproject.toml`
3. Docker images built and orchestrated via compose
