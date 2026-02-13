# Appointment Scheduler Backend

Django REST Framework backend for the Appointment Scheduling System.

## Architecture

```
backend/
├── scheduler/          # Django project settings
├── core/              # User model & base functionality
├── authentication/    # SSO & JWT authentication
├── slots/             # Faculty availability slots
├── bookings/          # Student bookings
├── manage.py
├── requirements.txt
└── Dockerfile
```

## Features

- **SSO Integration**: Seamless authentication with PBL platform
- **Mock SSO Mode**: Development without PBL dependency
- **JWT Authentication**: Secure token-based auth
- **Role-based Access**: Student and Faculty permissions
- **Slot Management**: Faculty creates availability slots
- **Booking System**: Students book appointments
- **Transaction Safety**: Race condition prevention

## Quick Start

### 1. Setup Environment

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your settings
# For development, minimal changes needed - mock SSO works out of the box
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Unix)
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 4. Run Development Server

```bash
python manage.py runserver 8000
```

## API Endpoints

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/sso/` | GET | SSO entry point (redirect from PBL) |
| `/api/v1/auth/sso/verify/` | POST | Verify SSO token (returns JSON) |
| `/api/v1/auth/sso/mock/` | GET | Generate mock SSO URL (dev only) |
| `/api/v1/token/refresh/` | POST | Refresh JWT token |

### Users

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/users/me/` | GET | Get current user profile |
| `/api/v1/users/health/` | GET | Health check |

### Slots (Faculty)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/slots/faculty/` | GET | List faculty's slots |
| `/api/v1/slots/faculty/` | POST | Create new slot |
| `/api/v1/slots/faculty/{id}/` | GET | Get slot details |
| `/api/v1/slots/faculty/{id}/` | PUT | Update slot |
| `/api/v1/slots/faculty/{id}/` | DELETE | Delete slot |

### Slots (Student)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/slots/available/` | GET | List available slots |
| `/api/v1/slots/available/{id}/` | GET | Get slot details |

### PBL Integration (Availability Summary)

This endpoint is intended for the main PBL site (server-to-server) to display whether
each subject currently has any available slots created by teachers.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/slots/availability-summary/` | GET | Boolean per subject: has any future unbooked slots |

**Auth (required in production)**

- Set `PBL_SCHEDULER_SHARED_SECRET` in the backend environment.
- Call with header: `X-PBL-Scheduler-Secret: <shared-secret>`

**Response shape**

```json
{
  "generated_at": "2026-02-13T12:00:00Z",
  "subjects": [
    {"subject": "Web Development", "has_available_slots": true},
    {"subject": "Compiler Design", "has_available_slots": false}
  ]
}
```

### Bookings (Student)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/bookings/student/` | GET | List student's bookings |
| `/api/v1/bookings/student/` | POST | Create booking |
| `/api/v1/bookings/student/current/` | GET | Get current active booking |
| `/api/v1/bookings/student/{id}/cancel/` | POST | Cancel booking |

### Bookings (Faculty)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/bookings/faculty/` | GET | List bookings on faculty's slots |

## SSO Modes

### Mock Mode (Development)

Set in `.env`:
```
SSO_MODE=mock
```

Generate mock SSO URL:
```bash
curl "http://localhost:8000/api/v1/auth/sso/mock/?role=student"
```

Visit the returned `sso_url` to simulate login.

Mock token formats:
- Simple: `mock_student` or `mock_faculty`
- Full: `mock_student_123_john@example.com_John Doe`

### Real Mode (Production)

Set in `.env`:
```
SSO_MODE=real
PBL_API_URL=https://pbl.example.com/api
PBL_API_KEY=your-api-key
```

Expected PBL API response:
```json
{
  "success": true,
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "name": "User Name",
    "role": "student"
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Django debug mode | `False` |
| `SECRET_KEY` | Django secret key | - |
| `DATABASE_URL` | Supabase PostgreSQL URL | - |
| `SSO_MODE` | `mock` or `real` | `mock` |
| `PBL_API_URL` | PBL platform API URL | - |
| `PBL_API_KEY` | API key for PBL | - |
| `STUDENT_FRONTEND_URL` | Student panel URL | `http://localhost:5173` |
| `FACULTY_FRONTEND_URL` | Faculty panel URL | `http://localhost:5174` |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | - |
| `CANCELLATION_WINDOW_HOURS` | Hours before slot when cancel is blocked | `24` |

## Database (Supabase)

### Connection

1. Create project at [supabase.com](https://supabase.com)
2. Get connection string from Settings > Database
3. Set `DATABASE_URL` in `.env`

### Tables Created by Migrations

- `users` - User accounts (students & faculty)
- `slots` - Faculty availability slots
- `bookings` - Student appointments

## Deployment (Render)

This repo includes a ready-to-use Render blueprint at [render.yaml](../render.yaml).

### Backend (Render Web Service)

1. Create a new **Web Service** on Render from this GitHub repo
2. Render should auto-detect the blueprint; otherwise set:
  - **Root Directory**: `backend`
  - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
  - **Start Command**: `gunicorn scheduler.wsgi:application --bind 0.0.0.0:$PORT`

### Required Environment Variables (Render)

- `SECRET_KEY`
- `DATABASE_URL` (Supabase Postgres connection string)
- `ALLOWED_HOSTS` (comma-separated, e.g. `scheduler-backend.onrender.com`)
- `CORS_ALLOWED_ORIGINS` (comma-separated Vercel URLs)
- `CSRF_TRUSTED_ORIGINS` (optional; needed for Django admin over HTTPS)

### Optional Environment Variables

- `SSO_MODE` (`mock` or `real`)
- `PBL_API_URL`, `PBL_API_KEY` (when `SSO_MODE=real`)
- `STUDENT_FRONTEND_URL`, `FACULTY_FRONTEND_URL`

## Testing

```bash
# Run tests
python manage.py test

# With coverage
coverage run manage.py test
coverage report
```

## Security Notes

- All sensitive data in environment variables
- JWT tokens expire (configurable)
- Role-based permissions enforced server-side
- CORS properly configured
- API key required for PBL integration
- Transaction-safe booking to prevent race conditions
