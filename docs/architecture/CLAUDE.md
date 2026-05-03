# Architecture Folder

Contains finalized architecture and design documentation for the project.

## Contents
- `README.md` — Project overview and component summary
- `system-overview.md` — System architecture, sub-APIs, data flow
- `backend.md` — Backend conventions, data modeling, LLM client
- `frontend.md` — Frontend overview and core principles (entry point for the frontend doc set)
- `frontend-state.md` — MobX rules, state ladder, observer/useState/useEffect rules, async resource trio
- `frontend-pages.md` — Page lifecycle, route ownership, URL-driven loads, query-param persistence
- `frontend-components.md` — Component rules, generic vs page-aware, splitting growing components
- `frontend-api.md` — `api/` layer, `models/` DTOs, `client.ts`, no runtime validation
- `frontend-forms.md` — Draft state, validation as computed, submit flow, server vs client errors
- `frontend-layout.md` — Folder structure, what lives where, grep rules
- `dev-environment.md` — Development setup, ports, tooling
- `deployment.md` — Docker services, nginx config, production routing
- `auth.md` — JWT authentication, roles, shared login flow
- `quick-reference.md` — Condensed technical reference (DB models, API endpoints, tools, patterns)

## Rules
- This folder is for **final, approved** documentation only
- Draft/planning docs belong in `docs/plans/`
- Keep docs concise and up-to-date as the project evolves
- **Hard limit: every architecture file stays under 300 lines.** If a topic doesn't fit, split it into multiple cohesive files (see the `frontend*.md` set as a worked example: `frontend.md` overview + per-area deep dives). `quick-reference.md` is the only intentional exception — it is dense by design.

