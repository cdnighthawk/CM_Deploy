# USIS CM Mobile (Expo)

Field app for USIS Construction Management: email/password sign-in, project list, and offline drawing-set cache.

## Prerequisites

- Node.js 20+
- Expo Go on a device, or Android Studio / Xcode for emulators
- Running [USIS CM backend](../backend) with migration `0040_mobile_refresh_tokens` applied

## Setup

```bash
cd mobile
cp .env.example .env
# Edit EXPO_PUBLIC_API_BASE to your Flask URL
npm install
npm start
```

### API base URL

| Environment | `EXPO_PUBLIC_API_BASE` |
|-------------|------------------------|
| Android emulator | `http://10.0.2.2:5000` |
| iOS simulator | `http://127.0.0.1:5000` |
| Physical device (LAN) | `http://<your-pc-lan-ip>:5000` |
| Render | `https://<your-service>.onrender.com` |

## Backend mobile auth

The app uses:

- `POST /api/v1/auth/mobile/login` — `{ email, password }`
- `POST /api/v1/auth/mobile/refresh` — `{ refresh_token }`
- `POST /api/v1/auth/mobile/logout` — `{ refresh_token }`

Apply migrations:

```bash
cd ../backend
flask db upgrade
```

## EAS builds

```bash
npx eas-cli login
npx eas build --profile preview --platform android
```

Profiles are defined in `eas.json` (`development`, `preview`, `production`).

## Manual test checklist

1. Sign in with a valid USIS user (bootstrap admin or registered account).
2. Open **Projects** and pull to refresh.
3. Open a project → **Drawings** → select a set → **Download set** on Wi‑Fi.
4. Enable airplane mode → open a cached sheet (PDF viewer).
5. Sign out → confirm login screen returns.

## Logo

Branding uses `assets/images/usis-eagle-logo.png` (same asset as the web shell).
