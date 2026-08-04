# StyleMate Authentication Plan

Replace the hardcoded `DEMO_USER_ID=1` identity used across the codebase with a
full JWT-based auth system on the FastAPI backend and the Expo/React Native
frontend, backed by Supabase/Postgres.

## Scope

In scope: register, login, refresh (with rotation), logout, global auth
middleware/dependency, protected navigation, removal of every hardcoded
`user_id=1` / `DEMO_USER_ID` reference.

Out of scope (separate follow-ups): password reset, social login.

## Architecture decisions

| Topic | Decision |
| --- | --- |
| Password hashing | bcrypt, cost factor 12 |
| Tokens | JWT (HS256), access 15 min, refresh 7 days |
| Refresh token storage | SHA-256 hash in `refresh_tokens` table (never raw) |
| Refresh rotation | Each `/auth/refresh` revokes the old token, issues a new pair (replay-safe) |
| Login rate limiting | Redis (`login_fail:{email}`, 5 attempts / 15 min) with in-memory fallback |
| Auth placement | `get_current_user` FastAPI dependency applied to every non-`/auth/*` router |
| User routes | Standardized on `/users/me` (no `user_id` in path/query/header) |
| Register `name` | Optional; defaults to the email prefix (`users.name` is NOT NULL) |
| Frontend token storage | `expo-secure-store` (never AsyncStorage) |
| Frontend refresh | Single-flight silent refresh in the API client; queue requests while refreshing |

## Backend work

### 1. Dependencies (`requirements.txt`)
- Add `bcrypt`, `email-validator`, `PyJWT`.

### 2. Database migration (`alembic/versions/b3c5d7e9f1a3_add_auth_tables.py`)
- Add nullable `users.password_hash` (existing rows migrate cleanly).
- Create `refresh_tokens` table: `id`, `user_id` (FK), `token_hash`
  (unique, SHA-256), `expires_at`, `revoked`, `revoked_at`, `created_at`.

### 3. Auth module (`server/app/auth/`)
- `security.py` — bcrypt hash/verify, JWT encode/decode (with random `jti` so
  tokens issued in the same second are unique), `refresh_token_hash()`,
  constant-time `tokens_match()`.
- `rate_limit.py` — Redis-backed login attempt limiter with in-memory fallback.
- `dependencies.py` — `get_current_user` decodes the Bearer access token and
  returns the `User`.

### 4. Auth router (`server/app/routers/auth.py`)
- `POST /auth/register` — validate email + password strength (>=8 chars, 1
  uppercase, 1 digit), 409 on duplicate email, bcrypt-hash, issue token pair.
- `POST /auth/login` — rate-limited (429 + `Retry-After`), verify credentials,
  issue pair.
- `POST /auth/refresh` — verify signature + expiry + DB hash match + not
  revoked, then rotate (revoke old, issue new pair).
- `POST /auth/logout` — delete the refresh-token row.

### 5. Global protection (`server/app/main.py`)
- Include `auth` router unprotected; every other router gets
  `dependencies=[Depends(get_current_user)]`.
- Remove the demo-user seed block.

### 6. Router de-hardcoding (replace `user_id=1` / `X-User-ID` with auth)
- `users.py` — `/users/me` endpoints; delete `X-User-ID` header & owner bypass.
- `calendar.py` — analytics/repeat-check/list/create use current user;
  `update_entry` + `link_try_on_image` ownership check; **fix `user_id=1`
  auto-create in `link_try_on_image`.**
- `outfits.py` — suggestions/smart/weather/capsule use current user;
  **`/outfit-feedback` sets `user_id` from auth and verifies item ownership.**
- `style_advice.py` — **`/explain-outfit` and `/style-advice` verify item
  ownership** (403 on foreign items).
- `clothing.py` — list/create use current user; get/update/delete/suggestions/
  complete-outfit ownership checks.
- `tryon.py` — replace `X-User-ID` header with `get_current_user`;
  `results`/`usage` drop `{user_id}` (use current user); poll ownership check.
- `shopping.py`, `packing.py`, `fashion_rating.py` — use current user.
- `style_match.py`, `shop_matches.py` — verify `item_id` ownership.

### 7. Schemas (`server/app/schemas.py`)
- Add `RegisterIn`, `LoginIn`, `RefreshIn`, `LogoutIn`, `TokenPair`,
  `RegisterResponse`.
- Strip `user_id` from create/request bodies (`ClothingItemCreate`,
  `CalendarEntryCreate`, `OutfitFeedbackIn`, `SmartOutfitIn`, `CapsuleRequest`,
  `PackingRequest`, `RatingRequest`).

## Frontend work

### 1. Dependency & config
- Add `expo-secure-store` + `app.json` plugin entry.

### 2. `lib/auth.tsx` (new)
- `AuthProvider` / `useAuth`: load tokens from SecureStore on launch
  (`isLoading`), expose `user`, `signIn`, `signUp`, `signOut`.

### 3. `lib/api.ts`
- Authenticated client: attach `Authorization: Bearer`, single-flight silent
  refresh on 401 (queue concurrent requests), clear tokens + redirect to login
  if refresh fails.
- Add `authApi` (register/login/refresh/logout).
- Remove `DEMO_USER_ID` and all `user_id` args (`usersApi`, `consentApi`,
  `tryOnApi.results/usage` now call `/users/me` and `/try-on/results`).

### 4. Screens & navigation
- New `login.tsx`, `register.tsx`.
- Root `_layout.tsx`: wrap in `AuthProvider`; show AuthNavigator (login/register)
  when unauthenticated, existing tabs/stack when authenticated.

## Verification

- `alembic upgrade head` against a scratch DB; backend auth smoke test
  (register → login → refresh → replay → logout → rate-limit).
- Run existing `server/tests`.
- Frontend: `npx tsc --noEmit` + `expo lint`.
