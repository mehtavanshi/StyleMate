# StyleMate — Step-by-Step AI Build Prompts

## How to use this

- Give these to an AI coding agent **one step at a time**, not all at once. Wait for each step to finish, run/test the app, then move to the next.
- Best tool for this: an agentic coding tool that can create files and run commands directly in a project folder (e.g. Claude Code). A plain chat window works too, but you'll have to copy code manually.
- Each step is self-contained. Copy the text inside the code block and paste it as your prompt.
- Steps are grouped into phases. Finish a phase before starting the next — later prompts assume earlier ones exist.
- Keep a single project folder for the whole build so the AI can see previous files when you paste the next prompt.

---

## PHASE 0 — Project Setup

### Step 0.1 — Initialize the project

```
Create a new project called "StyleMate" with two folders:
- /app : a React Native app using Expo (TypeScript)
- /server : a Python FastAPI backend

Set up /app with Expo Router and basic navigation with 4 empty screens:
Home, Wardrobe, Add Item, Outfit Suggestions.

Set up /server with FastAPI, a health check endpoint at /health,
SQLite database using SQLAlchemy, and a requirements.txt.

Create a README.md explaining how to run both the app and the server locally.
```

### Step 0.2 — Create a project context file

```
Create a file called PROJECT_CONTEXT.md at the root of the project.
In it, summarize: what StyleMate is (an AI wardrobe and outfit-pairing app),
the tech stack (React Native/Expo frontend, FastAPI/SQLite backend),
and the planned features (wardrobe scanning, AI tagging, outfit pairing,
calendar, body type filter, shopping suggestions, virtual try-on, hairstyle try-on).
Keep this file updated as a running summary every time we add a major feature,
so future prompts have context.
```

---

## PHASE 1 — MVP: Wardrobe + AI Tagging + Pairing

### Step 1.1 — Database models

```
In /server, create SQLAlchemy models for:
- User (id, name, email, gender, style_preference)
- ClothingItem (id, user_id, image_url, category, color, pattern,
  occasion_tag, season, created_at)

Add a database migration/init script and a seed script with 5 sample
clothing items for testing.
```

### Step 1.2 — Image upload endpoint

```
In /server, add a POST /upload-image endpoint that accepts an image file,
saves it to a local /uploads folder (create a helper so this can be swapped
for cloud storage like S3 or Cloudinary later), and returns the image URL.
Add basic validation for file type and size.
```

### Step 1.3 — AI tagging endpoint

```
In /server, add a POST /tag-item endpoint that:
1. Accepts an image URL
2. Sends it to an AI vision model with a prompt asking it to return
   JSON with: category (top/bottom/dress/outerwear/footwear/accessory),
   dominant_color, pattern (solid/striped/printed/checked/other),
   occasion_tag (casual/office/ethnic/party/formal/loungewear), and season.
3. Parses and returns that JSON.

Use an environment variable for the AI API key. Add clear error handling
if the AI response isn't valid JSON (retry once, then return a fallback
"unclassified" tag set rather than crashing).
```

### Step 1.4 — Connect "Add Item" screen

```
In /app, build the "Add Item" screen:
1. Let the user take a photo or pick one from the gallery
2. Upload it to POST /upload-image
3. Send the returned URL to POST /tag-item
4. Show the AI's suggested tags in editable fields (category, color,
   pattern, occasion, season) so the user can correct them
5. On confirm, save the item via a new POST /clothing-items endpoint
   in the backend, then navigate back to the Wardrobe screen

Add a loading state while the AI is tagging, and an error state if it fails.
```

### Step 1.5 — Wardrobe screen

```
In /app, build the Wardrobe screen as a grid of clothing items pulled from
GET /clothing-items (create this endpoint in /server if it doesn't exist).
Each item shows its photo and category. Add filter chips at the top for
category and occasion_tag. Tapping an item opens a detail view with all
its tags and a delete button (wire up DELETE /clothing-items/{id}).
```

### Step 1.6 — Rule-based pairing engine

```
In /server, create a new module pairing_engine.py with a function
suggest_outfits(user_id, occasion_tag=None) that:
1. Loads the user's clothing items
2. Groups them by category (top, bottom, footwear, accessory)
3. Scores combinations using simple rules:
   - neutral colors (black/white/beige/grey/navy) pair with anything
   - same color family (monochrome) is a safe high score
   - complementary colors (basic color wheel opposites) score well
   - clashing bright patterns together score low
   - if occasion_tag is given, only use items matching that tag
4. Returns the top 5 scored outfit combinations as JSON,
   each with a short plain-English reason for the pairing

Add a GET /outfit-suggestions endpoint that calls this function.
Write 3-4 unit tests for the scoring logic using sample items.
```

### Step 1.7 — Outfit Suggestions screen

```
In /app, build the Outfit Suggestions screen that calls
GET /outfit-suggestions and displays each suggested outfit as a card
showing the paired items' photos side by side, plus the reason text
underneath. Add a refresh button to re-generate suggestions.
```

**Checkpoint:** At this point you have a working MVP — scan clothes, get tagged, get outfit suggestions. Test it fully before moving on.

---

## PHASE 2 — Calendar, Body Type, Feedback Loop

### Step 2.1 — Calendar/occasion planning

```
In /server, add a CalendarEntry model (id, user_id, date, occasion_tag,
locked_outfit_id nullable) and endpoints: POST /calendar-entries,
GET /calendar-entries, PATCH /calendar-entries/{id}.

In /app, build a Calendar screen where the user taps a date, picks an
occasion_tag from a dropdown, and gets outfit suggestions filtered to
that occasion (reuse /outfit-suggestions with the occasion_tag param).
Let the user "lock in" a suggested outfit for that date.
```

### Step 2.2 — Body type input

```
In /server, add a body_type field to the User model with options
(rectangle, hourglass, pear, apple, inverted_triangle). Add a
POST /users/{id}/body-type endpoint to set it manually via a simple
questionnaire for now (skip photo-based detection — we'll add that later
if needed). In /app, add a short onboarding questionnaire screen for this.
```

### Step 2.3 — Bias suggestions using body type

```
In /server, update pairing_engine.py so suggest_outfits also takes the
user's body_type and gives a small score boost to items/silhouettes
that are commonly recommended for that body type (e.g. wrap styles and
belted waists score higher for "rectangle" and "apple" body types).
Keep this as a simple additive scoring rule, not a separate model.
```

### Step 2.4 — Like/dislike feedback loop

```
In /server, add an OutfitFeedback model (id, user_id, outfit_item_ids,
liked boolean, created_at) and a POST /outfit-feedback endpoint.
Update suggest_outfits to slightly boost scores for color/category
combinations the user has liked before, and lower scores for ones
they've disliked, based on their feedback history.

In /app, add thumbs up/down buttons to each outfit suggestion card
that call this endpoint.
```

---

## PHASE 3 — Shopping Suggestions

### Step 3.1 — Flipkart affiliate integration

```
In /server, create a new module shopping_service.py with a function
search_flipkart(query: str) that calls the Flipkart Affiliate API
(use environment variables FLIPKART_AFFILIATE_ID and
FLIPKART_AFFILIATE_TOKEN) and returns product name, image, price,
and affiliate link for the top 5 results. Add error handling for
rate limits and API failures with a graceful empty-result fallback.
```

### Step 3.2 — "Complete the look" gap detection

```
In /server, add a function in pairing_engine.py called find_gaps(user_id)
that looks at the user's wardrobe and detects missing categories or weak
combinations (e.g. lots of tops but no matching neutral bottoms).
For each gap, generate a short shopping search query describing the
ideal item (e.g. "beige wide leg trousers women") using an AI text call.
Add a GET /shopping-suggestions endpoint that runs find_gaps and then
calls search_flipkart for each gap, returning combined results.
```

### Step 3.3 — Shopping UI

```
In /app, add a "Complete the Look" section to the Outfit Suggestions
screen that calls GET /shopping-suggestions and shows product cards
(image, price, name) that open the affiliate link in the browser when tapped.
```

> Note: check the current Amazon affiliate API docs before integrating — Amazon has been migrating affiliates from the old Product Advertising API to a newer "Creators API," so confirm which one is live when you get to this step. Meesho does not currently offer a public product-search affiliate API, so skip direct integration there for now; a simple "search on Meesho" deep link is a reasonable placeholder.

---

## PHASE 4 — Virtual Try-On

### Step 4.1 — Photo capture + consent

```
In /app, build a "My Photo" screen where the user uploads a full-body
photo for try-on purposes. Before allowing upload, show a clear consent
screen explaining the photo will be used only for virtual try-on
rendering and can be deleted anytime. Add a "delete my photo" button
that calls a new DELETE /users/{id}/photo endpoint in /server.
```

### Step 4.2 — Try-on API integration

```
In /server, create try_on_service.py with a function generate_tryon(
user_photo_url, garment_image_url) that calls a virtual try-on API
(use an environment variable TRYON_API_KEY; structure the function so
the provider — e.g. FASHN.ai or Kling — can be swapped via a config
value). Add a POST /try-on endpoint. Add per-user rate limiting
(max 5 generations per day) stored in a new TryOnUsage table.
```

### Step 4.3 — Try-on UI

```
In /app, add a "Try It On" button on each outfit suggestion card that
calls POST /try-on and shows a loading spinner, then displays the
rendered image full-screen with save/share buttons. Show a friendly
message if the user hits their daily rate limit.
```

### Step 4.4 — Hairstyle try-on (optional add-on)

```
In /server, extend try_on_service.py with generate_hairstyle_tryon(
user_photo_url, hairstyle_reference) using the same pattern as the
clothing try-on function. In /app, add a simple hairstyle picker
(grid of preset style thumbnails) on the try-on result screen that
lets the user preview a hairstyle change on the same rendered photo.
```

---

## PHASE 5 — Polish & Publish

### Step 5.1 — Privacy & settings

```
In /app, build a Settings screen with: privacy policy link, "delete my
account and all data" button (wire this to a new DELETE /users/{id}
endpoint in /server that cascades and deletes all related records and
uploaded photos), and a toggle for notifications.
Draft a plain-language privacy policy page explaining what photos are
stored, why, and how to delete them.
```

### Step 5.2 — Polish pass

```
Review the whole /app codebase and add: loading skeletons for all
data-fetching screens, empty states (e.g. "Your wardrobe is empty,
add your first item" with a CTA button), and consistent error toasts
for failed API calls. Do not change any business logic, only UX polish.
```

### Step 5.3 — Build configuration

```
Set up EAS Build configuration in /app for both Android and iOS,
including app icon and splash screen placeholders, app name "StyleMate",
and a proper bundle identifier. Create a BUILD.md explaining the exact
commands to build and submit to both the Play Store and App Store.
```

### Step 5.4 — Store listing content

```
Write Play Store and App Store listing content for StyleMate: a short
description (under 80 characters), a full description (under 4000
characters), and 5 suggested screenshot captions describing what each
screenshot should show.
```

---

## Tips for running this well

- Test after every single step before moving to the next — small steps are easy to debug, big batches aren't.
- If a step fails or produces something broken, just describe the error back to the AI in your next message rather than re-pasting the whole step.
- Keep API keys out of your prompts — tell the AI to use environment variables, and set the actual values yourself in a `.env` file.
- Phases 3 and 4 depend on external accounts (Flipkart Affiliate Program, a try-on API provider) — sign up for those before you reach that step so you have real keys ready.
