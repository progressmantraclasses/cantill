# Corvo PR → PO

Employees raise purchase requests (PRs) by chat; the app decides — by following the **versioned procurement policy stored
as data** — whether to place a purchase order (PO) directly or start a sourcing request (RFQ / RFP). Uploading a new
policy version changes decisions with **no code change**.

- **Repository:** https://github.com/progressmantraclasses/cantill
- **Hosted app:** _add Vercel URL_ · **API:** _add Render URL_ (free tier sleeps: open it once before use)
- **Stack:** Flask + SQLAlchemy (served by uvicorn) · React 18 + Vite · SQLite locally / Postgres (Supabase) in production ·
  optional Gemini for AI features

Design notes: [`DECISIONS.md`](DECISIONS.md) (every judgement call where the policy was silent) ·
[`APPROACH.md`](APPROACH.md) (how the system is built).

---

## Contents

1. [Prerequisites](#prerequisites)
2. [Get the code](#get-the-code)
3. [Run with Docker (one command)](#run-with-docker-one-command)
4. [Run without Docker](#run-without-docker)
5. [Environment variables](#environment-variables)
6. [Using the app](#using-the-app)
7. [API](#api)
8. [Blind-test procedure](#blind-test-procedure)
9. [Deploy (free tier)](#deploy-free-tier)
10. [Project layout](#project-layout)

---

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Git | any | cloning |
| Docker Desktop | 24+ | the one-command run |
| Python | 3.11 | backend without Docker |
| Node.js | 20+ (tested on 22) | frontend without Docker |

## Get the code

```bash
git clone https://github.com/progressmantraclasses/cantill.git
cd cantill
```

## Run with Docker (one command)

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| UI | http://localhost:8080 |
| API health | http://localhost:8000/api/health |

Postgres runs in its own container; tables and seed data are created on first start.

Enable the optional AI features by passing a Gemini key:

```bash
# macOS / Linux / Git Bash
GEMINI_API_KEY=your-key docker compose up --build
```

```powershell
# Windows PowerShell
$env:GEMINI_API_KEY="your-key"; docker compose up --build
```

Stop with `Ctrl+C`, then `docker compose down` (add `-v` to also wipe the database volume).

## Run without Docker

Use two terminals, both starting from the repo root (`cantill/`).

### 1. Backend — terminal 1

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example .env          # optional: edit it to add GEMINI_API_KEY / DATABASE_URL
python -m uvicorn app.asgi:application --port 8000
```

> If PowerShell blocks `Activate.ps1`, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**macOS / Linux / Git Bash**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate               # Git Bash on Windows: source .venv/Scripts/activate
pip install -r requirements.txt
cp ../.env.example .env                 # optional: edit it to add GEMINI_API_KEY / DATABASE_URL
python -m uvicorn app.asgi:application --port 8000
```

The API is now on http://localhost:8000/api/health. With `DATABASE_URL` empty it uses SQLite (`backend/cantill.db`),
created and seeded automatically on first start. Delete that file to reset to the original kit data.

**Run the tests** (from `backend/`, venv active):

```bash
python -m pytest tests -q
```

### 2. Frontend — terminal 2

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to `http://localhost:8000`, so no frontend env is needed locally.

Production build: `npm run build` (output in `frontend/dist/`), preview with `npm run preview`.

### Seed data

Loaded on first start from `data/`: item master, suppliers, PO history, plants, the contract register, the two PDF-only
contracts (read from `data/contracts/pdf`) and policy v5.0.

## Environment variables

All variables are listed in [`.env.example`](.env.example). For local runs copy it to `backend/.env`.
`.env` files are git-ignored — never commit real keys.

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | backend | empty → SQLite | Postgres / Supabase connection string |
| `GEMINI_API_KEY` | backend | empty | Enables AI chat extraction, policy reading, contract-PDF fallback |
| `GEMINI_MODEL` | backend | `gemini-2.5-flash` | Gemini model name |
| `CORS_ORIGINS` | backend | `*` | Comma-separated origins allowed to call the API |
| `DATA_DIR` | backend | `<repo>/data` | Folder the seed data is read from |
| `VITE_API_URL` | frontend (build time) | empty → same origin | Public URL of the backend |

Everything works without a Gemini key: regex chat extraction, the manual policy editor and the template PDF parser.

## Using the app

| Screen | Who | Next action |
|---|---|---|
| Raise a request | Requester | chat, then **Confirm PR** |
| PR batches | Buyer | upload CSV → **Process batch** → **Export CSV** |
| Buyer workspace | Buyer | **Approve** (creates PO / RFQ / RFP) or **Override** (comment required) |
| Policy | Procurement | upload an amendment or describe a change → review changes + impact → **Approve** |
| Contracts | Buyer | add a PDF-only contract (extract from PDF, or manual) |
| Preferred suppliers | Buyer | pick a date → **Export top 3 as CSV** |
| Audit log | anyone | who did what, when |

Pick your name and role at the bottom of the left menu (there is no login; see `DECISIONS.md` §M).

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | liveness check |
| POST | `/api/process-batch` | CSV (multipart `file`, or raw body) → decisions JSON. `?format=csv` returns the section-4 CSV; `?policy_version=5.0` forces a version |
| GET | `/api/batches/<id>/export.csv` | decisions of a stored batch as CSV |
| POST | `/api/batches/<id>/reprocess` | re-run a stored batch under the current policies (body `{"policy_version": "x"}` to force one) |
| GET | `/api/preferred-suppliers?as_of=YYYY-MM-DD[&format=csv]` | `item_code,rank,supplier_id,reference_price` (top 3) |
| POST | `/api/policies/drafts` | amendment file (`file`), `{text}` or `{document}` → draft with plain-language changes + impact |
| POST | `/api/policies/drafts/<id>/approve` | activate from its effective date (Procurement only) |
| GET / POST | `/api/contracts`, `/api/contracts/extract` | register / add / extract from PDF |
| POST | `/api/chat`, `/api/chat/confirm` | chat intake |

Send `X-User` and `X-Role` (`Requester` / `Buyer` / `Procurement`) headers; policy changes need `Procurement`.

Example — process the sample batch and save the decisions (run from the repo root):

```bash
curl -X POST -H "X-User: me" -H "X-Role: Buyer" \
  -F file=@data/pr_batches/sample_pr_batch.csv \
  "http://localhost:8000/api/process-batch?format=csv" -o decisions.csv
```

> On Windows PowerShell use `curl.exe` (not the `curl` alias) and put the command on one line.

## Blind-test procedure

1. **Run 1:** PR batches → upload batch → **Export CSV**.
2. **Run 2:** Policy (as Procurement) → upload the amendment → read the plain-language changes → **Approve** → PR batches →
   **Reprocess with current policy** → **Export CSV**.
   If the amendment's effective date is later than the batch dates, the batch is still decided under the older version by
   design (`DECISIONS.md` §H). To force the new version:
   `POST /api/batches/<id>/reprocess` with `{"policy_version": "<new>"}`.
3. **Supplier lists:** Preferred suppliers → set the date → **Export**.

## Deploy (free tier)

1. **Supabase** — create a project and copy the **pooler** connection string.
2. **Render** (Web Service, Docker) — connect this repo; root = repo root, Dockerfile path `backend/Dockerfile`.
   Env: `DATABASE_URL`, `GEMINI_API_KEY`, `CORS_ORIGINS=https://<your-vercel-app>.vercel.app`.
   Tables and seed data are created on first start.
3. **Vercel** — import this repo; project root `frontend`, framework **Vite**,
   env `VITE_API_URL=https://<render-service>.onrender.com`.

Then put both URLs at the top of this README.

## Project layout

```
cantill/
├── backend/
│   ├── app/
│   │   ├── engine/        pure decision engine (no I/O)
│   │   ├── policy/        policy schema, diff, amendments + v5_0.json
│   │   ├── services/      LLM (Gemini), chat intake, PDF extraction
│   │   ├── api/           Flask endpoints
│   │   ├── models.py      SQLAlchemy models
│   │   ├── seed.py        loads data/ on first start
│   │   └── asgi.py        uvicorn entry point
│   ├── tests/             pytest suite (engine + API)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/pages/         one file per screen
│   ├── src/api.js         API client (uses VITE_API_URL)
│   ├── nginx.conf         static serving in the Docker image
│   └── Dockerfile
├── data/                  kit data the app seeds from (master_data, contracts, pr_batches)
├── master_data/ contracts/ pr_batches/   original task kit as delivered (same files as data/)
├── *.pdf, README.txt      original task brief, policy v5.0 and worked examples
├── DECISIONS.md           judgement calls and why
├── APPROACH.md            architecture and approach
├── docker-compose.yml
└── .env.example
```
