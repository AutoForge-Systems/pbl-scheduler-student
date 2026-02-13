# PBL → Scheduler: Subject Slot Availability API (Shareable)

This document is for the **PBL website owner/team**.
It explains how to call the Scheduler backend endpoint to know **per subject** whether **any slots are available** right now.

## 1) Endpoint

- Method: **GET**
- Path: `/api/v1/slots/availability-summary/`

Full URL example:

- `https://<SCHEDULER_DOMAIN>/api/v1/slots/availability-summary/`

## 2) Authentication (Shared Secret)

This is **server-to-server** auth using a shared secret header.

Send this header on every request:

- `X-PBL-Scheduler-Secret: <PBL_SCHEDULER_SHARED_SECRET>`

Important:
- The scheduler team will generate the secret and provide it to you **out-of-band** (chat/phone/password manager).
- Do **not** commit/store the real secret in public places.

### 2.1) Which “key” do you need?

The “API key” you need from the scheduler team is the value of:

- `PBL_SCHEDULER_SHARED_SECRET`

You will use it as the request header:

- `X-PBL-Scheduler-Secret: <PBL_SCHEDULER_SHARED_SECRET>`

The scheduler team will send you the real value privately. Paste it into your PBL backend environment/config.

## 3) What the API returns

Response is JSON with a boolean for each allowed subject.

Example response:

```json
{
  "generated_at": "2026-02-13T12:00:00Z",
  "subjects": [
    {"subject": "Web Development", "has_available_slots": true},
    {"subject": "Compiler Design", "has_available_slots": false}
  ]
}
```

Meaning:
- If `has_available_slots` is `true` → at least one slot exists that is:
  - in the future
  - `is_available = true`
  - not booked with a `confirmed` booking
- If `false` → no such slots exist right now for that subject.

## 4) Example request (curl)

```bash
curl -H "X-PBL-Scheduler-Secret: <YOUR_SHARED_SECRET>" \
  "https://<SCHEDULER_DOMAIN>/api/v1/slots/availability-summary/"
```

## 5) Common error responses

- `403 Forbidden` → missing/incorrect `X-PBL-Scheduler-Secret`
- `503 Service Unavailable` → Scheduler backend is not configured with `PBL_SCHEDULER_SHARED_SECRET` (production safety)

## 6) Suggested usage on PBL side

- Call from your backend (not from browser JS) to keep the shared secret private.
- Cache the result for a short time (e.g., 30–60 seconds) to avoid too many requests.
