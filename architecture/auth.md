# Authentication

## Approach

JWT (JSON Web Tokens) — stateless authentication shared across both SPAs.

## Flow

1. User submits credentials (login form — shared between User and Admin SPAs)
2. Backend validates credentials against SQLite user store
3. Backend issues a JWT containing user ID and role
4. Client stores JWT (localStorage or httpOnly cookie — TBD)
5. All subsequent API requests include the JWT
6. Backend validates JWT on each request

## Roles

| Role | User SPA | Admin SPA | Admin API |
|------|----------|-----------|-----------|
| user | Full access | No access | No access |
| admin | Full access + admin link | Full access | Full access |

## Shared Login

The login component/flow is the **only shared code** between User SPA and Admin SPA. Both apps:

- Use the same login endpoint (`/api/auth/login`)
- Receive the same JWT format
- Store and send tokens the same way

After login, each SPA diverges into its own UI and functionality.

## Admin Link

When an admin user is logged into the User SPA, a link to the Admin SPA (`/admin`) is displayed in the UI.
