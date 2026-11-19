# Corvo PR → PO

Employees raise purchase requests by chat; the app decides, by following the **versioned procurement policy stored as
data**, whether to place a PO or start a sourcing request. Uploading a new policy version changes decisions with no code change.

Hosted app: **<add Vercel URL>** · API: **<add Render URL>** (free tier sleeps: open once before use)

## Run locally (one command)

```bash
docker compose up --build
# UI  http://localhost:8080      API  http://localhost:8000/api/health
```

Optional: `GEMINI_API_KEY=... docker compose up --build` enables AI policy reading and chat slot extraction
(everything also works without a key: regex chat extraction, manual policy editor, template PDF parser).

### Without Docker

```bash
# backend (SQLite by default; set DATABASE_URL for Postgres/Supabase)
cd backend && pip install -r requirements.txt
python -m uvicorn app.asgi:application --port 8000      # creates tables and seeds the kit data on first start
python -m pytest tests -q

# frontend
cd frontend && npm install && npm run dev                 # http://localhost:5173 (proxies /api to :8000)
```

Seeded on first start: item master, suppliers, PO history, plants, the contract register, the two PDF-only contracts
(read from `data/contracts/pdf`) and policy v5.0.

## Using it

| Screen | Who | Next action |
|---|---|---|
| Raise a request | Requester | chat, then **Confirm PR** |
| PR batches | Buyer | upload CSV → **Process batch** → **Export CSV** |
| Buyer workspace | Buyer | **Approve** (creates PO / RFQ / RFP) or **Override** (comment required) |
| Policy | Procurement | upload amendment or describe a change → review changes + impact → **Approve** |
| Contracts | Buyer | add a PDF-only contract (extract from PDF, or manual) |
| Preferred suppliers | Buyer | pick a date → **Export top 3 as CSV** |
| Audit log | anyone | who did what, when |

Pick your name and role at the bottom of the left menu (no login; see DECISIONS.md §M).

## API

| Method | Path | |
|---|---|---|
| POST | `/api/process-batch` | CSV (multipart `file`, or raw body) → decisions JSON. `?format=csv` returns the section-4 CSV. `?policy_version=5.0` forces a version |
| GET | `/api/batches/<id>/export.csv` | decisions of a stored batch as CSV |
| POST | `/api/batches/<id>/reprocess` | re-run a stored batch under the current policies |
| GET | `/api/preferred-suppliers?as_of=YYYY-MM-DD[&format=csv]` | `item_code,rank,supplier_id,reference_price` (top 3) |
| POST | `/api/policies/drafts` | amendment file (`file`), `{text}` or `{document}` → draft with plain-language changes + impact |
| POST | `/api/policies/drafts/<id>/approve` | activate from its effective date (Procurement) |
| GET/POST | `/api/contracts`, `/api/contracts/extract` | register / add / extract from PDF |
| POST | `/api/chat`, `/api/chat/confirm` | chat intake |

Send `X-User` and `X-Role` (`Requester`/`Buyer`/`Procurement`) headers; policy changes need `Procurement`.

```bash
curl -X POST -H "X-User: me" -F file=@data/pr_batches/sample_pr_batch.csv "http://localhost:8000/api/process-batch?format=csv" > decisions.csv
```

### Blind-test procedure

1. **Run 1:** PR batches → upload batch → Export CSV.
2. **Run 2:** Policy (as Procurement) → upload the amendment → read the plain-language changes → Approve → PR batches →
   **Reprocess with current policy** → Export CSV. (If the amendment's effective date is later than the batch dates, the batch
   is still decided under the older version by design: DECISIONS.md §H. Reprocess forcing the new version:
   `POST /api/batches/<id>/reprocess {"policy_version": "<new>"}`.)
3. **Supplier lists:** Preferred suppliers → set the date → Export.

## Deploy (free)

1. **Supabase:** create a project, copy the pooler connection string.
2. **Render (web service, Docker):** root = repo, Dockerfile path `backend/Dockerfile`; env `DATABASE_URL`, `GEMINI_API_KEY`,
   `CORS_ORIGINS=https://<your-vercel-app>`. Tables and seed data are created on first start.
3. **Vercel:** project root `frontend`, framework Vite, env `VITE_API_URL=https://<render-service>.onrender.com`.

## Layout

`backend/app/engine` pure decision engine · `backend/app/policy` policy schema/diff/amend + `v5_0.json` ·
`backend/app/services` LLM, chat, PDF · `backend/app/api` endpoints · `frontend/src/pages` screens · `data/` the kit.
See `DECISIONS.md` and `APPROACH.md`.
