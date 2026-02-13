# Scheduler Backend (Django)

This is the Django REST API that powers the Student + Faculty portals.
It also supports integration with the main PBL website for SSO and for showing
“subject slots available” status.

## What this backend does

- **SSO login** (mock mode for dev, real mode for production)
- **JWT auth** for Student/Faculty portals
- **Slots**: faculty create time slots
- **Bookings**: students book slots (with business rules)
- **PBL integration**: a server-to-server endpoint that tells PBL whether each subject currently has any available slots

## Folder map

```text
backend/
  scheduler/          Django settings + urls
  core/               User model + shared helpers
  authentication/     SSO + JWT
  slots/              Slot CRUD + student visibility rules
  bookings/           Booking rules + faculty actions
  manage.py
```

## Quick start (local)

1. Create env file

```bash
cp .env.example .env
```

1. Install + migrate

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python manage.py migrate
```

1. Run

```bash
python manage.py runserver 8000
```

## Core API endpoints

### Authentication

| Endpoint | Method | Description |
| --- | ---: | --- |
| `/api/v1/auth/sso-login/` | GET | Final step of SSO login (exchanges token for JWTs) |
| `/api/v1/auth/sso/mock/` | GET | Generate a mock SSO URL (dev only, when `SSO_MODE=mock`) |
| `/api/v1/token/refresh/` | POST | Refresh JWT |

### Slots

| Endpoint | Method | Description |
| --- | ---: | --- |
| `/api/v1/slots/faculty/` | GET/POST | Faculty list/create slots |
| `/api/v1/slots/faculty/{id}/` | GET/PUT/DELETE | Faculty slot detail/update/delete |
| `/api/v1/slots/available/` | GET | Student sees available slots (filtered by assignment rules) |

### Bookings

| Endpoint | Method | Description |
| --- | ---: | --- |
| `/api/v1/bookings/student/` | GET/POST | Student list/create booking |
| `/api/v1/bookings/student/{id}/cancel/` | POST | Student cancel booking |
| `/api/v1/bookings/faculty/` | GET | Faculty bookings list |

## PBL integration: “subject slots available”

PBL needs a simple way to show something like:

> Web Development: slots available ✅

This backend provides a server-to-server endpoint for that.

### Endpoint

`GET /api/v1/slots/availability-summary/`

It returns a boolean per allowed subject, based on whether there exists **any** slot that is:

- in the future
- `is_available=true`
- not currently booked (not `booking.status=confirmed`)

### Auth (production)

This endpoint is *not* authenticated with a user JWT because the main PBL site is a different system.
Instead, it uses a shared secret header.

- Configure on Scheduler backend: `PBL_SCHEDULER_SHARED_SECRET=<random-strong-string>`
- PBL calls with header: `X-PBL-Scheduler-Secret: <same-string>`

### Example request

```bash
curl -H "X-PBL-Scheduler-Secret: <YOUR_SHARED_SECRET>" \
  https://<YOUR-SCHEDULER-DOMAIN>/api/v1/slots/availability-summary/
```

### Example response

```json
{
  "generated_at": "2026-02-13T12:00:00Z",
  "subjects": [
    {"subject": "Web Development", "has_available_slots": true},
    {"subject": "Compiler Design", "has_available_slots": false}
  ]
}
```

## Secrets / “API keys” (important)

There are two different secrets people often confuse:

1. `PBL_API_KEY`
   - Used by **this scheduler backend** to call **PBL’s APIs**.
   - Usually the PBL team provides this to you.
   - Do not commit it.

2. `PBL_SCHEDULER_SHARED_SECRET`
   - Used by **PBL website** to call **this scheduler backend** endpoint `/api/v1/slots/availability-summary/`.
   - You generate this value.
   - This is the value you share with the PBL site owner.

Never paste real secrets into this README or git history. Put them in Render environment variables or in `.env` locally.

## SSO modes

### Development

```dotenv
SSO_MODE=mock
```

### Production

```dotenv
SSO_MODE=real
PBL_API_URL=...
PBL_API_KEY=...
```

## Deployment (Render)

Use the blueprint at [render.yaml](../render.yaml).

Render should auto-detect the blueprint; otherwise set:

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
- Shared secret required for the PBL availability summary endpoint
- Transaction-safe booking to prevent race conditions
