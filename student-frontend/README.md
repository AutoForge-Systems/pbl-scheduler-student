# Student Scheduler Frontend

React + Vite + TailwindCSS frontend for students to book appointments with faculty.

## Features

- **SSO Authentication**: Auto-login via PBL platform redirect
- **View Available Slots**: Browse all available time slots
- **Book Appointments**: Book one slot at a time
- **Cancel Bookings**: Cancel with configurable time window
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

App runs at `http://localhost:5173`

## Development with Mock SSO

1. Start the backend server
2. Visit `http://localhost:8000/api/v1/auth/sso/mock/?role=student`
3. Click the returned `sso_url` to simulate login
4. You'll be redirected to the student panel with auth tokens

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
│   ├── AvailableSlots.jsx
│   ├── Dashboard.jsx
│   └── MyBooking.jsx
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
| `/` | Dashboard with booking summary |
| `/slots` | Browse and book available slots |
| `/booking` | View and manage current booking |
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
