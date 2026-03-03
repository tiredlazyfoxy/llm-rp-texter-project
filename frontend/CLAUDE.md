# Frontend

Vite multi-page application — TypeScript, React, MobX.

## Applications
- **User SPA** (served at `/`) — Player-facing chat interface
- **Admin SPA** (served at `/admin`) — World and user management

## Setup
- Bundler: Vite with separate entry points per SPA
- State management: MobX
- Routing: History API (back/forward button support)
- Dev server: `npx vite --port 8094`

## Key Constraints
- User and Admin SPAs are separate apps with separate builds
- They share **only** the login/auth flow
- Admin link shown in User SPA for admin-privileged users
- Dev: Vite proxies `/api` to localhost:8085
- Prod: nginx serves static builds, proxies `/api` to backend
