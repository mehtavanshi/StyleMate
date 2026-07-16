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

The API will be available at **http://127.0.0.1:8000**.

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → returns `{"status": "ok"}`
- Interactive API docs (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

On first run, SQLAlchemy will automatically create a local SQLite database file (`stylemate.db`) inside `/server`, based on the models defined in `app/models.py`.

---

## Connecting the app to the server

By default, mobile devices/simulators can't reach `127.0.0.1` on your computer directly:

- **iOS simulator:** `http://127.0.0.1:8000` works as-is.
- **Android emulator:** use `http://10.0.2.2:8000` instead.
- **Physical device (Expo Go):** use your computer's local network IP, e.g. `http://192.168.1.23:8000` (find it with `ipconfig` on Windows or `ifconfig`/`ipconfig getifaddr en0` on macOS). Make sure your phone and computer are on the same Wi-Fi network.

You'll likely want to store this base URL in a config file or environment variable in the app once you start wiring up real API calls.

---

## Next steps

- Build out the UI for each of the four screens in `/app/app/(tabs)`.
- Add more SQLAlchemy models and API routes in `/server/app` (e.g. wardrobe items, outfits, users).
- Add request/response schemas with Pydantic for your API endpoints.
- Wire up the app screens to call the FastAPI backend.
