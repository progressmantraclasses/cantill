# DECISIONS.md

Where the brief, the policy (v5.0) or the data was silent or ambiguous, this is what I noticed, what I decided and why.
Every decision below is implemented; where a number or behaviour is a policy parameter it lives in the policy JSON
(`backend/app/policy/v5_0.json`), not in code.

## A. Supplier ranking (policy 6.2: "the exact weighting is yours")

**Formula** (all components 0..1, then weighted; weights are stored in the policy under `params.preferred.weights`):

`score = 0.30·PO count + 0.25·recency + 0.20·contract + 0.10·on-time + 0.15·quality`

| Component | Definition | Why |
|---|---|---|
| PO count | POs for the item in the 548 days ÷ the highest count on that item's list | Repeat business is the best proof a supplier delivers *this* item. Relative to the item's own list so a busy item doesn't flatten everything. |
| Recency | 1.0 if last PO ≤ 90 days ago, 0.5 if ≤ 365, else 0 (same bands as the worked examples) | A supplier we used last month is more likely to still stock and price it. |
| Contract | 1 if the supplier has ever held a contract for the item that started on/before the date (even if expired) | Policy 6.1/6.2: a negotiated rate is a trust signal, and expired contracts still count. |
| On-time | `on_time_pct / 100` from supplier master | Delivery reliability. Deliberately light: it is a supplier-level number, not item-level. |
| Quality | `quality_rating / 5` | Same reasoning. |

Ties: more recent last PO first, then lower supplier id (so output is deterministic).
**Reference price** (6.3): price on the supplier's most recent PO in the 548 days, else the rate of its most recent
contract. **Why these weights:** history of buying the item (count + recency = 55%) matters most for a *direct PO without
quotes*; supplier-wide ratings (25%) are tie-breakers, not drivers; contract is a clear signal (20%). I checked the weights
against the three buyer lists in the worked examples (ITM-1048, ITM-1036, ITM-1016); all three reproduce exactly (unit
tests `test_preferred_lists_match_worked_examples`). The buyer sees every component per supplier in the workspace and on
the *Preferred suppliers* screen.

**Top-up for sourcing (6.4):** other Active suppliers in the item's category ranked by `0.5·on-time + 0.5·quality`
(reproduces examples 10 and 12). A short list gives fewer suppliers than 3/5 (example 11 shows 4), never a padded one
with ineligible suppliers.

## B. Lines I do not process (route `NOT_PROCESSED`)

| Situation in the data | Decision | Reason |
|---|---|---|
| Quantity 0 (PR-26-00172) | NOT_PROCESSED | A zero quantity is not a requirement. Processing it would produce a PO for ₹0 or distort clubbing. |
| Plant not in plant master, e.g. `PUN2` (PR-26-00173) | NOT_PROCESSED | The policy applies to PUN1/CHK1 only. Guessing the plant could put a PO on the wrong site. |
| Missing/invalid quantity, dates, pr_no, or neither item code nor description | NOT_PROCESSED with the exact reason | Cannot be valued or clubbed. |
| Duplicate `pr_no`+`pr_line` | The second one is NOT_PROCESSED | Same key twice is a data error, not a second need. |

Each gets a reason in the export so a buyer can fix and resubmit. They are never silently dropped (186 in, 186 out).

## C. Matching items (policy 1.1)

* A valid item code wins. An item code that is **not** in the master falls back to the description and is flagged.
* Free text is normalised (lower-case, `×`→`x`, `24"`→`24 inch`, hyphens split, noise phrases such as
  "for maintenance", "as per sample", "urgent", "(repeat)" removed, short forms `brg/hyd/pneu/rod` expanded; all of this is
  policy data) then scored by token overlap (Dice). A size/grade the request has but the item lacks (e.g. `6308` vs `6205`)
  halves the score, so "brg 6205" never matches the 6308 bearing. Below 0.6 → new item.
* "Ultrasonic thickness gauge" and "Drinking water purifier 50 LPH" are not in the master, so they are NEW and valued at
  qty × the requester's estimate.
* **Chat:** the assistant never names an item the matcher did not return. 2+ typed words that all appear in exactly one item
  name auto-match ("nitrile gloves"); otherwise it shows up to 3 candidates; otherwise it says it will not guess and offers a
  new-item request.
* Item matching for a new item with **no estimated price**: value 0 and a flag for the buyer. It still goes to sourcing
  because rule 1.2 comes first.

## D. Clubbing (policy 2)

* "Within 14 calendar days" compares **dates** (created date minus first line's created date), not 336 hours.
* A line is compared with the **first line** of each requirement (as written), never with the latest one, so a chain of
  lines can't drift. A line that qualifies for several requirements joins the earliest.
* Clubbing keys include plant, so PR-26-00106 (PUN1) and PR-26-00103 (CHK1) stay separate (example 6).
* UoM is not a clubbing key. UoM in a PR that disagrees with the master was not seen in the data; if it appeared I would
  flag rather than convert.
* **Near-duplicates** (same item and plant created minutes apart, e.g. PR-26-00174/175, 4 minutes apart, qty 1 each): policy
  says club them, so they are clubbed (value is the sum). I add a "possible duplicate" flag for the buyer. I do not drop them
  because I cannot tell a duplicate from a genuine second unit.
* "Urgent" typed in the description while the urgency field says Normal: the **field wins** (policy says "marked
  Emergency"), and the buyer sees a warning flag. Emergency anywhere in a requirement makes the whole requirement an
  emergency (2.3).
* Multi-line PRs (PR-26-00164 …) are handled per line; lines of one PR can belong to different requirements.

## E. Contracts and valuation (policy 3, 4)

* **PDF-only contracts** (RC-2026-031, RC-2026-033): loaded at start-up by reading the signed PDFs (all 12 PDFs parse, 10
  match the register exactly), consumed value 0. Buyers can add more from the Contracts screen (PDF extract + review, or manual).
  Validity is by the **requirement date**, so the laptop requirement raised 16 Nov does *not* use RC-2026-033 (starts 20 Nov)
  even though a clubbed line was created on 20 Nov (2.3: requirement date = first line).
* **Blocked supplier's contract** (RC-2026-005, Metalink Alloys, Blocked) is ignored (4.1 needs an Active supplier).
  Aluminium plate (ITM-1006) therefore has no contract and is valued from the last PO or the standard price.
* **Ceiling ledger:** a batch run always starts from the register's consumed values and consumes in requirement-date order;
  a requirement consumes ceiling only if the contract rule actually fires. So Run 1 and Run 2 on the same batch are
  reproducible and the sequence in the batch matters exactly as policy 4.2 says.
* Equal rates between two usable contracts: lower contract id.
* **3.1 valuation** uses the most recent PO price in the 365 days **from any supplier** (3.1(b) says "the most recent PO", and
  unlike 5.3/5.4 does not require Active). The PO is then *priced* at the 1st preferred supplier's reference price (policy 5.3/5.4),
  so group value and unit price can differ slightly (examples 7 and 8 show exactly this).
* A contract rate is used as given (no UoM conversion).
* Ceiling test is `consumed + value ≤ cap` (inclusive, as written "must not exceed").

## F. Decision rules (policy 5)

* Order is the policy order. Thresholds: `≤ ₹5,00,000` (emergency) inclusive; `< ₹2,00,000` and `< ₹10,00,000` strict
  (RFP at exactly ₹10,00,000, per "or more").
* "Bought from an Active supplier in the last 365 days" = a PO in `[date-365, date]` whose supplier is Active **today**. A PO
  from a now-Blocked supplier does not count as proven supply (e.g. items only ever bought from S008/S011 go to RFQ).
* A PO rule that fires but cannot be carried out (no eligible preferred supplier) **falls through** to the next rule instead of
  making a PO to nobody. This is recorded in the decision.
* If no rule matches (only possible after a policy edit): RFQ for buyer review, flagged.
* 5.7 (never PO or suggest a Blocked/Inactive supplier) is enforced three times: preferred list, top-up, and again at approve/
  override time (an override naming a Blocked supplier is rejected).
* The Capex line "Needs capex approval" is a flag on the decision and the Approve button reads "capex sourcing request".

## G. PO consolidation (policy 7)

* Applies only to decision = PO. The window is measured from the **first requirement's** creation time on that PO (7.1), and a
  requirement joins the earliest open PO it qualifies for (7.2).
* Keys (`supplier_id`, `plant`, `route`) and the window are policy parameters.
* `group_id` = `REQ-0001…` and `po_id` = `PO-0001…`, both numbered in creation order of the first line, so the export is
  deterministic. My numbers need not equal the numbers in the worked examples (those are illustrative); the grouping does.

## H. Policy as data

* **Version in force** for a requirement = the approved version with the latest `effective_from` on or before the requirement
  date. Clubbing/matching use the version of the line's own date. So an amendment effective 1 Dec does not alter November
  requirements, and re-running a batch is always reproducible. `policy_version` can also be forced per call.
* An amendment is parsed by an LLM **only into a draft**. The structure is validated against a JSON schema (known facts,
  operators, routes, unique rule ids), the **diff is computed by code** (I don't trust a model's summary), an impact preview
  re-runs the latest uploaded batch, and a human approves. A draft that fails validation cannot be approved.
* If the model is unavailable or misreads the amendment, Procurement can edit the draft as JSON in the app; no deploy needed.
* A new kind of rule (one plant, one category, one urgency) is a new JSON rule placed at the right position. The tests do this.
* Only Procurement can create/approve policy changes; buyer actions need the Buyer role (see M).

## I. Buyer workspace

* Approving a requirement creates a PO id (`B<batch>-PO-xxxx`; requirements consolidated on one PO share it) or an RFQ/RFP/
  capex request id. A requirement can be actioned once; override needs a written reason (≥5 characters) and keeps the
  original decision beside the override (policy 8.1).
* Reviews are keyed by the requirement's set of PR lines, so reprocessing a batch under a new policy keeps earlier actions
  that still refer to the same lines.

## J. Chat intake

* The LLM (if configured) only extracts fields; replies are templated and dates are resolved in code against today's
  date (IST), so "next Friday" is deterministic. With no API key a regex extractor does the same job.
* Urgency defaults to Normal and is shown on the confirmation card. "Urgent/ASAP/breakdown" sets Emergency. The buyer sees
  both on the requirement.
* Chat PRs are appended to one rolling "Chat requests" batch and the engine re-runs over it, so chat PRs club with each
  other (people split needs by chat too).
* A need-by date in the past is refused.

## K. Preferred supplier export

`item_code, rank, supplier_id, reference_price`, top 3, Active suppliers only, as of the chosen date (default today),
under the policy version in force on that date. Items with no preferred supplier simply have no rows.

## L. Dates and time

All timestamps are treated as local plant time (IST); no time-zone conversion is applied to the CSV data.

## M. Security and access

No real login (out of scope for the task): a name and role are chosen in the UI and sent as headers. They are written to the
audit log with the time. Roles are enforced on the server for policy changes (Procurement only). I would add SSO before real use.

## N. Known limits

* GST is excluded everywhere (as the policy says).
* Gemini free tier is rate-limited; that is why every AI step has a non-AI path (manual policy editor, regex chat extraction,
  template PDF parser).
* The hosted free Render instance sleeps when idle; open it once before a demo.
