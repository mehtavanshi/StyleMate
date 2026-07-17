# Onboarding Questionnaire UI — Body Type

## Context

StyleMate infers a user's `body_type` to bias outfit suggestions (Phase 2.2 in
`plan.md`). The backend already has a `body_type` column (`server/app/models.py:17`)
and a `UserResponse.body_type` field (`server/app/schemas.py:15`), plus a validated
set of 5 values in `server/app/config.py:19`:

```
rectangle, hourglass, pear, apple, inverted_triangle
```

**Gap:** the `POST /users/{id}/body-type` endpoint does **not** exist yet
(`server/app/routers/users.py` only has list/create/get). This plan adds it.

The frontend (`/app`) is an Expo Router + React Native (TS) app. There is no
onboarding screen today. Decisions confirmed with user:

- **Placement:** standalone route `app/onboarding.tsx`, opened from Home (one-time
  via an `AsyncStorage` "seen onboarding" flag), NOT a tab.
- **Questions:** 4 visual questions mapped directly to one of the 5 valid types.
- **Icons:** inline SVG via `react-native-svg` (no external image assets).

Body types map to these 5 values; do NOT introduce new strings.

## Decisions / Design

### Inference logic (frontend, pure function)
Four single-select visual questions. Each option carries a weight toward body types.
A small scoring map picks the highest-scoring type:

1. **"Which is closest to your shoulder / hip balance?"**
   - Shoulders wider than hips → `inverted_triangle`
   - Hips wider than shoulders → `pear`
   - About equal → `rectangle` / `hourglass` (tie broken by Q2)
2. **"How defined is your waist?"**
   - Very defined (waist noticeably narrower) → `hourglass`
   - little/no definition → `apple` / `rectangle`
3. **"Where do you carry most of your weight?"**
   - Midsection → `apple`
   - Hips/thighs → `pear`
   - Evenly → `rectangle` / `inverted_triangle`
4. **"Which silhouette matches you best?"** (final tie-breaker, illustrative icons
   of the 5 shapes) → directly sets the type.

Implement as `scoreBodyType(answers): BodyType` in a local helper, returning one of
`VALID_BODY_TYPES`. Keep it deterministic and unit-testable.

### Backend endpoint (must add)
In `server/app/routers/users.py`, add:

```python
@router.post("/{user_id}/body-type", response_model=UserResponse)
def set_body_type(user_id: int, body_type: BodyTypeIn, db=Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    if body_type.body_type not in VALID_BODY_TYPES:
        raise HTTPException(400, f"Invalid body_type. Must be one of {VALID_BODY_TYPES}")
    user.body_type = body_type.body_type
    db.commit(); db.refresh(user); return user
```

- Add `BodyTypeIn` schema to `server/app/schemas.py`: `{ body_type: str }`
  (or reuse a `Literal` of the 5 values). Validate against `VALID_BODY_TYPES` from
  `server/app/config.py`.
- Export `VALID_BODY_TYPES` is already importable from `app.config`.
- Register endpoint under existing `router = APIRouter(prefix="/users", ...)`.

### Frontend API client
In `app/lib/api.ts`, extend `usersApi` (after the existing `get` at line 74):

```ts
setBodyType: (id: number, bodyType: string) =>
  apiFetch<User>(`/users/${id}/body-type`, {
    method: "POST",
    body: JSON.stringify({ body_type: bodyType }),
  }),
```
Reuse `DEMO_USER_ID = 1` (same pattern as other APIs).

### Screen: `app/onboarding.tsx`
- Use **react-hook-form** (`useForm` with `mode: "onChange"`), one field per question.
  Each field value = the option's body-type weight/key. Validate all 4 required
  before submit.
- Each question: a row of selectable `TouchableOpacity` cards, each containing an
  inline **SVG** (`react-native-svg`) silhouette + a plain-language label (no medical
  jargon, e.g. "Hips wider than shoulders").
- On submit: call `scoreBodyType(watch())` → `usersApi.setBodyType(DEMO_USER_ID, type)`.
  Show a loading state, on success set `AsyncStorage` flag `onboarding_complete` and
  `router.replace("(tabs)")` (or navigate back). On error: `Alert`/inline error.
- Style to match existing screens (white cards, `#f5f5f5` bg, rounded 12, elevation).

### Navigation / entry point
- Add `app/onboarding.tsx` as a Stack screen in `app/_layout.tsx` (mirror the
  `wardrobe/[id]` pattern, `headerShown: true, title: "About your shape"`).
- In `app/app/(tabs)/index.tsx`:
  - On mount, read `AsyncStorage` `onboarding_complete`. If not set, show a
    "Tell us your shape" CTA button → `router.push("/onboarding")`.
  - Otherwise show current placeholder content.

### Dependencies
- `npm install react-hook-form` in `/app`.
- `npm install react-native-svg` in `/app` (verify it supports Expo SDK ~54 /
  RN 0.81; if the published version requires a different RN peer, use the matching
  `react-native-svg@^15` line and run `expo install react-native-svg` if needed).
  Do NOT add other form/UI libs.

## Files to change
- `server/app/schemas.py` — add `BodyTypeIn`.
- `server/app/routers/users.py` — add `POST /{user_id}/body-type`.
- `app/package.json` — add `react-hook-form`, `react-native-svg` (via install).
- `app/lib/api.ts` — add `usersApi.setBodyType`.
- `app/_layout.tsx` — register `onboarding` Stack screen.
- `app/app/(tabs)/index.tsx` — CTA + onboarding flag check.
- **new** `app/onboarding.tsx` — questionnaire screen.
- **new** `app/onboarding/bodyShapeIcons.tsx` (or inline in same file) — SVG silhouettes.
- **new** `app/onboarding/scoreBodyType.ts` — pure scoring helper.

## Validation
- Frontend: TS compiles (`npx tsc --noEmit`); `npm run lint`.
- Backend: `uvicorn` boots; `POST /users/1/body-type` with a valid value returns the
  user with `body_type` set; invalid value returns 400; unknown user returns 404.
- Unit test: add `server/tests/test_body_type.py` covering valid/invalid/user-not-found
  for the new endpoint (mirror `tests/test_*` style).
- Manual: run `expo start`, press `w`/scan; Home shows CTA → onboarding → submit →
  flags stored → navigates to tabs; re-open Home shows no CTA.

## Risks / notes
- Endpoint name in task is `POST /users/{id}/body-type` (hyphen). FastAPI path
  `/users/{user_id}/body-type` works; confirm no route collision in `users.py`.
- `body_type` values are lower-case strings; keep frontend exactly matching
  `VALID_BODY_TYPES` to avoid 400s.
- AsyncStorage import: `import AsyncStorage from "@react-native-async-storage/async-storage"`
  — confirm it's already a dependency; if not, add via `expo install`.
