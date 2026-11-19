# APPROACH.md

## Architecture

```
React + Vite UI ──► Flask API (served by uvicorn) ──► Postgres (Supabase) / SQLite locally
                         │
                         ├─ engine/  pure Python: matching, clubbing, contracts, valuation,
                         │           preferred list, rules, consolidation, pipeline (no DB, no Flask, no LLM)
                         ├─ policy/  JSON schema + validation, deterministic diff, amendment reader
                         └─ services/ Gemini wrapper, chat slots, contract PDF extractor, batch runner
```

* **Policy as data:** rules and parameters are a JSON document per version (`policy_versions`). The engine is a generic
  condition evaluator over a catalogue of per-requirement facts. A policy amendment is a new version, never a code change.
* **Engine is deterministic and testable:** `pytest backend/tests` covers the worked examples, the three preferred lists,
  blocked suppliers, determinism, and an amendment changing decisions through data only.
* **AI is at the edges only:** chat slot reading, reading an amendment into a *draft*, PDF contract fallback. A human approves
  anything the AI proposes; the decision engine never calls an LLM.

## AI tools used

* **Claude Code (Anthropic)** wrote most of the code and tests with me, under my direction. I reviewed the engine logic against
  the policy clause by clause and own every decision in DECISIONS.md.
* **Google Gemini (free tier)** inside the app: reading policy amendment documents into draft policy JSON, extracting slots
  from chat messages, and as a fallback when a contract PDF does not match the template.

## Run

See README.md.
