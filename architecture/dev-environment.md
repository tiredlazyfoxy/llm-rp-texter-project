# Development Environment

## Prerequisites

- Python 3.13
- Node.js (LTS) + npm
- Git

## Services & Ports

| Service | Port | URL |
|---------|------|-----|
| FastAPI backend | 8085 | `http://localhost:8085` |
| Vite dev server (User + Admin SPA) | 8094 | `http://localhost:8094` |

## Backend Setup

- **Virtual environment**: local `.venv` in `backend/`
- **Dependency management**: `pyproject.toml`
- **Framework**: FastAPI with uvicorn
- **CORS**: Enabled for `http://localhost:8094` (dev only)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
```

## Frontend Setup

- **Bundler/Dev server**: Vite
- **Multi-page app**: Two entry points (user SPA at `/`, admin SPA at `/admin`)
- **State management**: MobX
- **Routing**: History API

```powershell
cd frontend
npm install
npx vite --port 8094
```

## CORS Configuration (Dev Only)

The FastAPI backend enables CORS in development to allow the Vite dev server to make API calls:

- Allowed origins: `http://localhost:8094`
- Allowed methods: all
- Allowed headers: all
- Credentials: true

In production, CORS is not needed — nginx proxies everything under the same origin.

## Vite Proxy (Dev)

Vite dev server should proxy `/api` requests to `http://localhost:8085` to match the production routing:

```typescript
// vite.config.ts
server: {
  port: 8094,
  proxy: {
    '/api': 'http://localhost:8085'
  }
}
```

With the proxy in place, CORS on the backend may not be needed in dev either — but it's kept as a fallback.
