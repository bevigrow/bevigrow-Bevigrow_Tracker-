# BeviGrow Coffee B2B Tracker

A premium coffee **export & import** management application for BeviGrow — daily
activity logging, customer/supplier records, quotation and shipment tracking,
proof uploads, and AI-assisted summaries powered by **Claude Haiku**.

```
├── backend/     FastAPI + SQLAlchemy + Neon PostgreSQL + JWT
├── frontend/    React + TypeScript + Tailwind + Framer Motion + GSAP + Three.js
└── render.yaml  One-click Render blueprint for both services
```

---

## Quick start (local)

**Prerequisites:** Python 3.11+, Node 20+.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
cp .env.example .env             # then edit .env

uvicorn app.main:app --reload --port 8000
```

The API comes up on <http://127.0.0.1:8000> with interactive docs at `/docs`.

On first boot it creates the tables, seeds the admin account, and — outside
production — loads twelve representative coffee accounts with interaction
history so the dashboard has something to show.

> **No `DATABASE_URL`?** The backend falls back to a local SQLite file so it
> still runs. Point it at Neon before deploying.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on <http://localhost:5173>. Vite proxies `/api` to the backend on port
8000, so no CORS setup is needed locally.

### 3. Sign in

| Field | Value |
|---|---|
| Email | `bevigrow@gmail.com` |
| Password | `Bevi@GROW30@` |

Change this immediately in any real deployment — set `SEED_ADMIN_PASSWORD`
before the first boot, since the admin row is only created once.

---

## Neon PostgreSQL

1. Create a project at [neon.tech](https://neon.tech).
2. Create two branches — `development` and `production` — so schema changes can
   be tried without touching live data.
3. Copy the **pooled** connection string for each and convert it to the
   SQLAlchemy/psycopg 3 form:

```env
DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOST/DBNAME?sslmode=require
DB_SCHEMA=bevigrow
```

Notes:

- The `+psycopg` suffix selects psycopg 3 (the `psycopg[binary]` package).
  Neon's dashboard gives you a plain `postgresql://` URL, which SQLAlchemy maps
  to psycopg **2** and fails with `ModuleNotFoundError: No module named
  'psycopg2'`. The app rewrites the scheme on load, so either form works.
- **Tables live in their own `bevigrow` schema**, not `public`. That lets the
  app share a Neon database with Neon Auth or an earlier prototype without
  table-name collisions. Set `DB_SCHEMA` to change it; leave it blank to use
  the default schema.
- `sslmode=require` is mandatory — Neon rejects unencrypted connections.
- Pooling is configured in `app/database.py` (`pool_size`, `max_overflow`,
  `pool_recycle`, `pool_pre_ping`) and tuned via environment variables.
  `pool_pre_ping` matters on Neon specifically: it drops idle connections, and
  pre-ping revalidates one before it is handed to a request.

### What is stored

| Table | Contents |
|---|---|
| `users` | Team members, roles (admin / manager / employee), hashed passwords |
| `contacts` | Customers (export) and suppliers (import), coffee requirement, status |
| `activities` | Daily interaction log + the AI-generated summary of each |
| `documents` | Uploaded proof — quotations, invoices, POs, screenshots, samples |
| `reminders` | Follow-ups, both manual and AI-suggested |
| `ai_insights` | Cached dashboard / weekly narratives, so refreshes don't re-bill |

---

## AI — Claude Haiku only

Every AI feature runs on **`claude-haiku-4-5`** ($1 / $5 per million tokens,
200 K context). Opus-tier models are deliberately not used anywhere in this
codebase — Haiku gives the low cost, fast response and business-quality prose
these features need.

| Feature | Endpoint | What it does |
|---|---|---|
| Interaction summary | `POST /api/ai/summarize` | Turns shorthand notes into a professional paragraph |
| Dashboard insights | `GET /api/ai/insights` | Bullet briefing on today's pipeline |
| Weekly highlights | `GET /api/ai/weekly` | Management readout of the last 7 days |
| Smart follow-ups | `GET /api/ai/suggestions` | Ranks accounts needing attention, with a reason and next action |
| Apply follow-ups | `POST /api/ai/suggestions/apply` | Converts suggestions into reminder rows |

**Cost control.** Dashboard and weekly narratives are cached for 30 minutes
(`CACHE_MINUTES` in `app/routers/ai_routes.py`); `?refresh=true` forces a new
generation.

**Graceful degradation.** If `ANTHROPIC_API_KEY` is unset or the API errors,
every function falls back to deterministic local logic. The app stays fully
usable and the UI says which mode it's in — nothing 500s because AI was
unavailable.

---

## Deploying to Render

Push to GitHub, then **New → Blueprint** and select the repo. `render.yaml`
defines both services.

### Backend — Web Service (Python 3.11)

```bash
# Build
pip install --upgrade pip && pip install -r requirements.txt
# Start
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Environment variables:

Render prompts for three secrets on import (everything else is set by the
blueprint):

```env
DATABASE_URL=<Neon pooled PostgreSQL URL>
ANTHROPIC_API_KEY=<Claude Haiku API key>
SEED_ADMIN_PASSWORD=<password for the seeded admin account>
```

`JWT_SECRET` is generated by Render. `CORS_ORIGINS` and the frontend's
`VITE_API_URL` are resolved from each other with `fromService`, so renaming a
service cannot break them.

**The blueprint runs on the free instance type**, which has two consequences:
uploaded documents live on an ephemeral filesystem and are lost on every
redeploy (database records in Neon are unaffected), and the service sleeps
after 15 minutes idle, making the next request take ~50 seconds. To make
uploads durable, switch the backend to `plan: starter`, add a `disk:` block
mounted at `/var/data`, and set `UPLOAD_DIR=/var/data/uploads`.

The backend deploys to the `singapore` region to sit beside the Neon database
in `ap-southeast-1`; running it in the default `oregon` region adds roughly
200 ms to every query.

### Frontend — Static Site

```bash
# Build
npm install && npm run build
# Publish directory
dist
```

```env
VITE_API_URL=https://bevigrow-backend.onrender.com
```

The blueprint adds an SPA rewrite (`/*` → `/index.html`) so deep links like
`/app/contacts/12` survive a refresh, plus long-lived cache headers on hashed
assets.

### After the first deploy

1. Set `SEED_ADMIN_PASSWORD` **before** the backend's first boot — the admin
   row is created once and not overwritten afterwards.
2. Update `CORS_ORIGINS` on the backend to the real frontend URL.
3. Update `VITE_API_URL` on the frontend to the real backend URL, then redeploy
   (Vite inlines it at build time — changing it needs a rebuild, not a restart).

---

## Authentication & user management

Sign-in is built into the app itself — there is no third-party auth vendor, no
Google Workspace dependency, and no service account. User records live in the
same Neon database as the trading data, so roles and business records never
drift apart.

### Sign-in methods

| Method | Enabled by | Notes |
|---|---|---|
| Email + password | always on | PBKDF2-SHA256 hashes; the plaintext is never stored |
| Google Sign-In | setting `GOOGLE_CLIENT_ID` | button is hidden when unset |

Google ID tokens are verified server-side against Google's published keys —
signature, expiry, issuer, and **audience**. The audience check is what stops a
token minted for any other website being replayed here. Unverified Google email
addresses are rejected so they cannot be used to claim an existing account.

### Roles

| Role | Can do |
|---|---|
| `admin` | Everything, including managing the team and assigning roles |
| `manager` | All trading data; can view the team but not change roles |
| `employee` | Log activity and manage accounts; no team access |

Every role check is enforced **in the API**, not only in the UI. Hiding a nav
link is a convenience; the server rejects the request regardless.

Built-in safeguards: an admin cannot deactivate, demote, or delete their own
account, and the last remaining admin cannot be deleted — so an instance can
never be locked out of its own administration.

### Adding and removing people — without sharing any credentials

1. Sign in as an admin → **Team**
2. **Add member** → name, email, temporary password, role
3. Send them the temporary password privately; they change it on **Profile**

To revoke access, use **Deactivate** rather than Delete — the person can no
longer sign in, but their logged interactions stay attached to the accounts
they worked on. Deleting removes the user row entirely.

Forgot a password? With SMTP configured, **Forgot password** emails a
single-use link that expires in an hour. Without SMTP, an admin sets a new
password from the Team page (the key icon). Reset tokens are stored **hashed**,
so a database leak cannot be replayed as a working link.

### Setting up Google Sign-In (optional, ~5 minutes)

1. Go to <https://console.cloud.google.com/apis/credentials>
2. **Create Credentials → OAuth client ID → Web application**
3. Under **Authorised JavaScript origins** add every origin the app is served
   from, e.g. `http://localhost:5173` and your Render frontend URL
4. Copy the **Client ID** (ends in `.apps.googleusercontent.com`) into
   `GOOGLE_CLIENT_ID`

You never need the client secret. Leave `ALLOW_SELF_SIGNUP=false` and Google
sign-in only works for people an admin has already invited — a Google account
alone does not grant access.

### Self sign-up

Off by default. Set `ALLOW_SELF_SIGNUP=true` to let people register themselves;
pair it with `ALLOWED_EMAIL_DOMAINS=yourcompany.com` so only your own domain
can register. New accounts land in `DEFAULT_SIGNUP_ROLE` (`employee`).

### Sessions

A JWT signed with `JWT_SECRET`, valid 12 hours, held in `localStorage`. Any
401 anywhere in the app clears it and returns the user to sign-in. Signing out
discards the token. Changing `JWT_SECRET` invalidates every existing session.

---

## Design

**Palette.** Espresso `#3B2416` · Dark Roast `#2A1A12` · Caramel `#C68B59` ·
Latte Cream `#F5E6D3` · Mocha `#6F4E37` · Coffee Gold `#D9A05B`.
Headings in Playfair Display, body in Inter.

**Chart palette is validated, not eyeballed.** The brand hues are too light to
read as data marks on the dark surface, so `src/lib/viz.ts` carries a separate
palette that was machine-checked for lightness band, chroma floor,
colour-vision-deficiency separation and contrast:

- categorical `#B8862F` / `#3B9FD8` / `#4FA96B` — worst CVD ΔE 16.5, contrast ≥ 3:1
- ordinal roast ramp `#82582F → #F0CE9B` — monotone lightness, ΔL ≥ 0.06 per step

Every chart also ships a table view, and the world map encodes magnitude with
both size and shade so it survives greyscale.

**Motion.** A Three.js coffee bean that cracks open on click or drag; a
GSAP ScrollTrigger sequence that builds a cappuccino layer by layer as you
scroll; Framer Motion for page and component transitions; ambient particles and
steam. All of it respects `prefers-reduced-motion` — the pour scene renders its
finished state rather than animating.

**Performance.** Three.js (950 kB) and GSAP live in their own chunks behind the
lazy-loaded landing page, so authenticated routes start from an ~84 kB entry
bundle (26 kB gzipped).

---

## API reference

Full interactive docs at `/docs` on the running backend.

| Group | Routes |
|---|---|
| Auth | `POST /api/auth/login` · `GET /api/auth/me` |
| Users | `GET/POST /api/users` · `PATCH/DELETE /api/users/{id}` |
| Contacts | `GET/POST /api/contacts` · `GET/PATCH/DELETE /api/contacts/{id}` · `GET /api/contacts/board/pipeline` · `GET /api/contacts/countries` |
| Activities | `GET/POST /api/activities` · `PATCH/DELETE /api/activities/{id}` · `POST /api/activities/{id}/summarize` |
| Documents | `GET/POST /api/documents` · `GET /api/documents/{id}/download` · `DELETE /api/documents/{id}` |
| Reminders | `GET/POST /api/reminders` · `PATCH/DELETE /api/reminders/{id}` |
| Dashboard | `GET /api/dashboard` · `GET /api/dashboard/leaderboard` |
| AI | `GET /api/ai/status` · `POST /api/ai/summarize` · `GET /api/ai/insights` · `GET /api/ai/weekly` · `GET /api/ai/suggestions` · `POST /api/ai/suggestions/apply` |
| Health | `GET /api/health` |

---

## Security notes

- Passwords are hashed with PBKDF2-SHA256 (pure Python — no native bcrypt wheel
  to fail on Render).
- JWTs are HS256, signed with `JWT_SECRET`, valid 12 hours. A 401 anywhere in
  the app clears the token and returns the user to sign-in.
- Uploads are restricted by extension and size, stored under server-generated
  UUID filenames, and every download re-resolves the path and verifies it is
  still inside `UPLOAD_DIR`.
- Team management (create / delete users, change roles) is admin-only; the API
  enforces this independently of the UI.
