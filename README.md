# StyleMate

A wardrobe and outfit-suggestion app, made up of two parts:

- **`/app`** — React Native mobile app built with [Expo](https://expo.dev) and [Expo Router](https://docs.expo.dev/router/introduction/), written in TypeScript.
- **`/server`** — Python backend built with [FastAPI](https://fastapi.tiangolo.com), using [SQLAlchemy](https://www.sqlalchemy.org) with a SQLite database.

```
StyleMate/
├── app/       # Expo React Native app
└── server/    # FastAPI backend
```

---

## Running the app (`/app`)

### Prerequisites
- [Node.js](https://nodejs.org) (LTS version, 18+)
- npm (comes with Node) or yarn
- The [Expo Go](https://expo.dev/go) app on your phone (easiest way to test), or an iOS/Android simulator

### Steps

```bash
cd app
npm install
npm start
```

This starts the Expo development server and shows a QR code in your terminal.

- **On your phone:** open the Expo Go app and scan the QR code.
- **iOS simulator:** press `i` in the terminal (macOS + Xcode required).
- **Android emulator:** press `a` in the terminal (Android Studio required).
- **Web browser:** press `w` in the terminal.

The app currently has four screens, wired up with Expo Router tab navigation:
- **Home**
- **Wardrobe**
- **Add Item**
- **Outfit Suggestions**

All four are currently empty placeholders, ready for you to build out.

---

## Running the server (`/server`)

### Prerequisites
- Python 3.9+
- pip

### Steps

```bash
cd server

# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload
```

### Database setup (after git pull)

The SQLite database (`stylemate.db`) and uploaded images (`uploads/`) are not tracked in git. After cloning/pulling:

```bash
cd server

# Create and activate venv (if not already done)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create tables + seed demo data
python scripts/init_db.py
python scripts/seed_db.py
```

`init_db.py` creates the `users` and `clothing_items` tables. `seed_db.py` creates a demo user with 5 sample wardrobe items.

The database file is created at `server/stylemate.db`. It's local-only and won't sync across devices — that's normal for development.

### Running the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at **http://127.0.0.1:8000**.

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → returns `{"status": "ok"}`
- Interactive API docs (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Uploaded images are served from `http://127.0.0.1:8000/uploads/` via FastAPI's StaticFiles mount.

---

## Connecting the app to the server

The base URL is configured in `app/config/api.ts`. Update the `android` value to your machine's LAN IP:

```typescript
android: "http://YOUR_LAN_IP:8000",
```

Find your LAN IP with:
```bash
ip addr show | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | cut -d/ -f1
```

- **Physical device (Expo Go):** use the LAN IP above. Phone and computer must be on the same Wi-Fi network.
- **Android emulator:** `http://10.0.2.2:8000` works by default.
- **iOS simulator:** `http://127.0.0.1:8000` works by default.

---

## Next steps

- Add outfit suggestions and pairing logic in `/app/app/(tabs)/outfit-suggestions`.
- Style and polish the existing screens (Home, Wardrobe, Add Item, Outfit Suggestions).
- Add more API routes in `/server/app/routers/` as needed.
