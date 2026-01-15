# Faculty Scheduler Frontend

React + Vite + TailwindCSS frontend for faculty to manage availability slots and view bookings.

## Features

- **SSO Authentication**: Auto-login via PBL platform redirect
- **Create Slots**: Set availability time slots
- **Manage Slots**: View, edit, delete availability
- **View Bookings**: See all student appointments
- **Responsive Design**: Works on desktop and mobile

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```
VITE_API_URL=http://localhost:8000/api/v1
```

### 3. Run Development Server

```bash
npm run dev
```

App runs at `http://localhost:5174`

## Development with Mock SSO

1. Start the backend server
2. Visit `http://localhost:8000/api/v1/auth/sso/mock/?role=faculty`
3. Click the returned `sso_url` to simulate login
4. You'll be redirected to the faculty panel with auth tokens

## Project Structure

```
src/
├── components/       # Reusable UI components
│   ├── Alert.jsx
│   ├── BookingCard.jsx
│   ├── Layout.jsx
│   ├── LoadingSpinner.jsx
│   └── SlotCard.jsx
├── context/          # React context providers
│   └── AuthContext.jsx
├── pages/            # Page components
│   ├── AuthCallback.jsx
│   ├── Bookings.jsx
│   ├── CreateSlot.jsx
│   ├── Dashboard.jsx
│   └── MySlots.jsx
├── services/         # API services
│   ├── api.js
│   └── scheduler.js
├── utils/            # Utility functions
│   └── dateUtils.js
├── App.jsx
├── index.css
└── main.jsx
```

## Authentication Flow

1. User clicks link from PBL platform
2. PBL redirects to: `{backend}/api/v1/auth/sso?token={sso_token}`
3. Backend verifies token and redirects to: `{frontend}/auth/callback?access=...&refresh=...`
4. Frontend stores tokens and loads user profile
5. User accesses protected routes

## Available Routes

| Path | Description |
|------|-------------|
| `/` | Dashboard with stats and quick actions |
| `/slots` | View and manage availability slots |
| `/slots/create` | Create new availability slot |
| `/bookings` | View all student bookings |
| `/auth/callback` | Handle SSO callback |

## Build for Production

```bash
npm run build
```

Output is in `dist/` folder.

## Deployment (Vercel)

1. Push to GitHub
2. Connect repo to Vercel
3. Set environment variable: `VITE_API_URL`
4. Deploy

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `VITE_API_URL` | Backend API URL | Yes |
| `VITE_ENV` | Environment (development/production) | No |
