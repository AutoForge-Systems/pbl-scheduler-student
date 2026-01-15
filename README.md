# Appointment Scheduling System

A production-ready appointment scheduling system designed for integration with PBL (Project Based Learning) platforms. Features separate panels for students and faculty with SSO authentication.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PBL Platform                                 │
│                    (External - Existing System)                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ SSO Token
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Scheduler Backend (Django)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │ SSO Handler │  │ JWT Auth    │  │ REST API                    │ │
│  │ - Mock Mode │  │ - Issue     │  │ - Slots (Faculty)           │ │
│  │ - Real Mode │  │ - Validate  │  │ - Bookings (Student)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────────┘ │
│                           │                                         │
│                           ▼                                         │
│              ┌─────────────────────────┐                           │
│              │   Supabase PostgreSQL   │                           │
│              │   - users               │                           │
│              │   - slots               │                           │
│              │   - bookings            │                           │
│              └─────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
                    │                           │
                    │ JWT                       │ JWT
                    ▼                           ▼
    ┌───────────────────────┐     ┌───────────────────────┐
    │   Student Frontend    │     │   Faculty Frontend    │
    │   (React + Vite)      │     │   (React + Vite)      │
    │   - View slots        │     │   - Create slots      │
    │   - Book appointment  │     │   - Manage slots      │
    │   - Cancel booking    │     │   - View bookings     │
    └───────────────────────┘     └───────────────────────┘
```

## 📁 Project Structure

```
2_pannel/
├── backend/                    # Django REST API
│   ├── scheduler/              # Django project config
│   ├── core/                   # User model & base
│   ├── authentication/         # SSO & JWT
│   ├── slots/                  # Availability slots
│   ├── bookings/               # Appointments
│   ├── requirements.txt
│   └── Dockerfile
├── student-frontend/           # Student React app
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── faculty-frontend/           # Faculty React app
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml          # Full stack deployment
├── docker-compose.dev.yml      # Development setup
└── README.md
```

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone and navigate
cd 2_pannel

# Start all services
docker-compose up -d

# Services will be available at:
# - Backend:          http://localhost:8000
# - Student Frontend: http://localhost:5173
# - Faculty Frontend: http://localhost:5174
```

### Option 2: Manual Setup

#### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Unix

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver 8000
```

#### 2. Student Frontend Setup

```bash
cd student-frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env

# Start dev server
npm run dev
```

#### 3. Faculty Frontend Setup

```bash
cd faculty-frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env

# Start dev server
npm run dev
```

## 🚢 Deployment (GitHub + Vercel + Render)

### 1) Push to GitHub

- Ensure secrets are not committed (this repo ignores `.env` and `node_modules/` via [.gitignore](.gitignore)).
- Push the repository to GitHub.

### 2) Deploy Backend on Render

- This repo includes a Render blueprint: [render.yaml](render.yaml)
- Create a new Render **Web Service** from the GitHub repo.
- Set environment variables on Render:
  - `DATABASE_URL` (Supabase)
  - `ALLOWED_HOSTS` (e.g. `scheduler-backend.onrender.com`)
  - `CORS_ALLOWED_ORIGINS` (the two Vercel frontend URLs)
  - `SECRET_KEY`

Backend URL will look like: `https://<service-name>.onrender.com`

### 3) Deploy Frontends on Vercel (2 projects)

Create **two** Vercel projects from the same repo:

- **Student** project
  - Root Directory: `student-frontend`
  - Build Command: `npm run build`
  - Output Directory: `dist`
  - Env var: `VITE_API_BASE_URL` = `https://<render-backend>.onrender.com/api/v1`

- **Faculty** project
  - Root Directory: `faculty-frontend`
  - Build Command: `npm run build`
  - Output Directory: `dist`
  - Env var: `VITE_API_BASE_URL` = `https://<render-backend>.onrender.com/api/v1`

Both frontends include [vercel.json](student-frontend/vercel.json) and [vercel.json](faculty-frontend/vercel.json) to support React Router deep links.

## 🔐 SSO Integration

### Mock Mode (Development)

The scheduler includes a mock SSO mode for development without PBL dependency.

```bash
# Generate mock SSO URL
curl "http://localhost:8000/api/v1/auth/sso/mock/?role=student"
# or
curl "http://localhost:8000/api/v1/auth/sso/mock/?role=faculty"

# Response includes sso_url - visit it to login
```

**Mock Token Formats:**
- Simple: `mock_student` or `mock_faculty`
- Full: `mock_student_123_john@example.com_John Doe`

### Real Mode (Production)

Configure in backend `.env`:

```env
SSO_MODE=real
PBL_API_URL=https://pbl.example.com/api
PBL_API_KEY=your-api-key
```

**Expected PBL API Response:**

```json
{
  "success": true,
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "name": "User Name",
    "role": "student"  // or "faculty"
  }
}
```

### SSO Flow

```
1. User logs into PBL platform
2. PBL redirects to: {backend}/api/v1/auth/sso?token={sso_token}
3. Backend verifies token with PBL (or uses mock)
4. Backend creates/updates local user record
5. Backend issues JWT tokens
6. Redirects to frontend: {frontend}/auth/callback?access=...&refresh=...
7. Frontend stores tokens and loads dashboard
```

## 📊 Database Schema

### Users Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| email | VARCHAR | Unique email |
| name | VARCHAR | Display name |
| role | VARCHAR | 'student' or 'faculty' |
| pbl_user_id | VARCHAR | External PBL user ID |
| is_active | BOOLEAN | Account status |

### Slots Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| faculty_id | UUID | FK to users |
| start_time | DATETIME | Slot start (UTC) |
| end_time | DATETIME | Slot end (UTC) |
| is_available | BOOLEAN | Availability status |

### Bookings Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| slot_id | UUID | FK to slots (unique) |
| student_id | UUID | FK to users |
| status | VARCHAR | confirmed/cancelled/completed |
| cancelled_at | DATETIME | Cancellation timestamp |

## 🔑 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/auth/sso/` | SSO entry (redirect from PBL) |
| POST | `/api/v1/auth/sso/verify/` | Verify SSO token (JSON) |
| GET | `/api/v1/auth/sso/mock/` | Generate mock SSO (dev only) |
| POST | `/api/v1/token/refresh/` | Refresh JWT token |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me/` | Get current user |
| GET | `/api/v1/users/health/` | Health check |

### Slots - Faculty
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/slots/faculty/` | List faculty's slots |
| POST | `/api/v1/slots/faculty/` | Create slot |
| GET | `/api/v1/slots/faculty/{id}/` | Get slot |
| PUT | `/api/v1/slots/faculty/{id}/` | Update slot |
| DELETE | `/api/v1/slots/faculty/{id}/` | Delete slot |

### Slots - Student
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/slots/available/` | List available slots |
| GET | `/api/v1/slots/available/{id}/` | Get slot details |

### Bookings - Student
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/bookings/student/` | List my bookings |
| POST | `/api/v1/bookings/student/` | Create booking |
| GET | `/api/v1/bookings/student/current/` | Get active booking |
| POST | `/api/v1/bookings/student/{id}/cancel/` | Cancel booking |

### Bookings - Faculty
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/bookings/faculty/` | List bookings on my slots |

## ⚙️ Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Django debug mode | `False` |
| `SECRET_KEY` | Django secret key | - |
| `DATABASE_URL` | PostgreSQL connection | - |
| `SSO_MODE` | `mock` or `real` | `mock` |
| `PBL_API_URL` | PBL platform API URL | - |
| `PBL_API_KEY` | API key for PBL | - |
| `STUDENT_FRONTEND_URL` | Student panel URL | `http://localhost:5173` |
| `FACULTY_FRONTEND_URL` | Faculty panel URL | `http://localhost:5174` |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | - |
| `CANCELLATION_WINDOW_HOURS` | Hours before slot when cancel blocked | `24` |

### Frontend Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL |

## 🚢 Deployment

### Supabase (Database)

1. Create project at [supabase.com](https://supabase.com)
2. Go to Settings → Database → Connection string
3. Use the connection string in `DATABASE_URL`

### Railway (Backend)

1. Connect GitHub repository
2. Set environment variables
3. Configure build command:
   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
   ```
4. Configure start command:
   ```bash
   gunicorn scheduler.wsgi:application --bind 0.0.0.0:$PORT
   ```

### Vercel (Frontend)

For each frontend:

1. Connect GitHub repository
2. Set root directory (`student-frontend` or `faculty-frontend`)
3. Set environment variable: `VITE_API_URL`
4. Deploy

### Environment Checklist for Production

```env
# Backend
DEBUG=False
SECRET_KEY=<secure-random-key>
DATABASE_URL=postgresql://...@db.supabase.co:5432/postgres
SSO_MODE=real
PBL_API_URL=https://pbl.yourcompany.com/api
PBL_API_KEY=<api-key>
STUDENT_FRONTEND_URL=https://student-scheduler.vercel.app
FACULTY_FRONTEND_URL=https://faculty-scheduler.vercel.app
CORS_ALLOWED_ORIGINS=https://student-scheduler.vercel.app,https://faculty-scheduler.vercel.app

# Frontend
VITE_API_URL=https://scheduler-backend.railway.app/api/v1
```

## 📋 Business Rules

- **One booking per student**: Students can only have one active booking at a time
- **One booking per slot**: Slots can only be booked once
- **No overlapping slots**: Faculty cannot create overlapping availability
- **Cancellation window**: Bookings cannot be cancelled within X hours of appointment (configurable)
- **UTC timezone**: All times stored and processed in UTC
- **Server-side validation**: All rules enforced in backend

## 🔒 Security

- JWT tokens for API authentication
- API key for PBL ↔ Scheduler communication
- Role-based permissions (student/faculty)
- CORS properly configured
- No frontend-only security
- Transaction-safe booking (prevents race conditions)
- Passwords not stored (SSO-only auth)

## 🧪 Testing

### Backend
```bash
cd backend
python manage.py test
```

### Frontend
```bash
cd student-frontend  # or faculty-frontend
npm run lint
```

## 📝 License

MIT
