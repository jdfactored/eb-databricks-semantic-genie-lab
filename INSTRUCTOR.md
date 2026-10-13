# Instructor Guide

Companion to `README.md` (student-facing) and `SOLUTIONS.md` (keep private).

---

## Before the cohort starts

**1. Catalog and grants.** Everything goes into `<DEFAULT_CATALOG>.<user>_semantic`. The catalog name is
written in exactly one place in this repository, `DEFAULT_CATALOG` in `notebooks/helpers/utils.py`;
nothing else in the repo (including this guide) repeats it. To get the exact statements for your
cohort, run this in any notebook inside the repo:

```python
from helpers import setup_schemas
setup_schemas.print_instructor_grants("jane.doe@yourcompany.com")
```

It prints, with your catalog filled in:

```sql
-- Option A: let lab users create their own schemas
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG <DEFAULT_CATALOG> TO `account users`;

-- Option B: pre-create a student's schema and hand it over
CREATE SCHEMA IF NOT EXISTS <DEFAULT_CATALOG>.jane_doe_semantic;
GRANT USE CATALOG ON CATALOG <DEFAULT_CATALOG> TO `jane.doe@yourcompany.com`;
GRANT ALL PRIVILEGES ON SCHEMA <DEFAULT_CATALOG>.jane_doe_semantic TO `jane.doe@yourcompany.com`;
```

`00-setup` reuses an existing schema, and when creation fails its error message prints both options
with the student's own names filled in.

**2. Genie prerequisites (Exercises 2–4).** Per student:

| Need | How |
|---|---|
| Databricks SQL entitlement (or Consumer access for Genie One only) | Workspace admin > Identity and access > Entitlements |
| CAN USE on one **serverless** (or pro) SQL warehouse | Warehouse > Permissions. One shared serverless warehouse is enough for a cohort. |
| Partner-powered AI features | Account admin, account console > Settings; also on at workspace level |

**3. Exercise 4 extras.** Each degrades gracefully if you skip it, but the exercise is richer with it:

| Feature | Status | Setup |
|---|---|---|
| Genie Ontology / citations | Public Preview | Check the workspace **Previews** page and the account console Previews page; turn on anything Genie Ontology related. |
| Certification | GA | Grant **ASSIGN** on the `system.certification_status` governed tag to `account users` (or the cohort group): Catalog Explorer > Governed tags > `system.certification_status` > Permissions. Without it, 3A prints the ask and students use 3B. |
| Pages | Beta | Account console > Previews > enable Pages. Create a domain such as **Lumen Training** in Discover and give the cohort access. Students save **draft** Pages, which only influence their own Genie One chats. |
| Genie One | GA | Nothing beyond the entitlement and warehouse above. Account-level Genie One can be disabled by account admins; workspace-level `/one` is what the lab uses. |

**4. Dry run.** Do a full run as a non-admin student account before the cohort. These were checked
against the current documentation but could not be executed outside a workspace:

- The metric view uses unqualified source columns (`order_total`, `status`, `customer_id`) next to
  joined tables that share some names (`customer_id`, `order_id`). The docs resolve unqualified names to
  the source; if a runtime disagrees, prefix them with `source.` in `semantic_model._YAML`.
- `ontology.set_certification` tries `SET TAG ON TABLE`, `SET TAG ON VIEW` and `ALTER VIEW ... SET TAGS`
  in turn; one should work on views.
- UI labels in Exercises 2–4 (Configure > Instructions, Benchmarks, citation icons) move between
  releases. The steps are written to tolerate small differences.
- `genie_agents.ask()` uses the Conversation API response shape documented at the time of writing.
  It is optional; the UI path is the primary one.

---

## Timing

| Notebook | Target | Where students lose time |
|---|---|---|
| `00-setup` | 3 min | Nothing, unless grants are wrong |
| `01` | 15 min | Challenge 1: indenting YAML (handled), and `refund_rate` as a percentage instead of a ratio |
| `02` | 12 min | Finding the warehouse; titling the agent exactly as printed (auto-discovery depends on it); Challenge 2 trying to JOIN the metric view directly |
| `03` | 12 min | Copying Genie's SQL; asking follow-ups in the same chat instead of a new one |
| `04` | 13 min | Waiting for ontology re-indexing; features not enabled |

Expect 55 minutes for a cohort that has its grants in place.

---

## What is planted in the data

Keep this list off the student branch if you want discovery to be genuine. Numbers are for the default
seed on the day setup runs; the window is relative to today and volumes depend only on the day index,
so the totals are the same whatever date the lab runs (if setup and the exercise run on the same day).

| Plant | Effect on "revenue, last 90 days" | Where students find it | Teaching point |
|---|---|---|---|
| `lab_refunds` is at refund-event grain; 43% of refunded orders have 2–3 partial refunds | Finance's join duplicates order totals | 01 Step 2 (fan-out query) | Fix grain once, upstream of every consumer |
| ~3% of gross is internal QA test orders (`is_test_order`) | Both raw queries include them | 01 Step 2 | Global `filter` in the metric view |
| ~4.5% of orders are cancelled | Excluded by both analysts, included by the legacy table | 01, 03 | Measure-level `FILTER (WHERE ...)` |
| `lab_daily_sales_summary.revenue`: gross incl. cancelled and test orders, stopped refreshing 3 days ago, comment "Daily revenue summary" | The highest number of all | 03 (raw agent), 04 (curation) | A column named `revenue` is bait; deprecate it |
| ~30% of customers churn mid-window | 30-day vs 90-day actives differ by ~1,000 | 01 Step 3 | One governed lookback |
| Region targets calibrated so APAC is furthest below target, by both $ and % (17-point margin) | | 02 Challenge | A dimension-grain lookup is safe next to a metric view |

Reference numbers (seed 42, validated offline in pandas and by executing the SQL shapes in sqlite):

| Definition | Revenue, last 90 days |
|---|---|
| Sales Ops raw query (gross incl. test orders) | $3,945,738 |
| Finance raw query (fan-out join) | $3,911,177 |
| Gross bookings (governed, not "revenue") | $3,819,693 |
| **Net revenue (governed)** | **$3,600,536** |
| Legacy `daily_sales_summary.revenue` | $4,003,980 |

Active customers: Marketing 30-day 2,295; CS 90-day 3,248; **governed 3,205**. All-time refund rate
6.13%. Data spans 6 or 7 calendar months depending on the run date (the check computes it).

The two analysts argue over a $35k gap while both are ~$330k above the governed figure. Use that line.

---

## Known sticking points

**01 Step 2 — "so Finance was closer?"** Students sometimes decide Finance "wins" because it is lower.
Ask what happens if refund instalments were split differently: the fan-out error depends on how many
refund events exist, not on how much was refunded. Being closer is luck.

**01 Step 5 — `dimensions` vs `fields`.** Current docs prefer `fields`; the lab uses `dimensions`
because it is what the Catalog Explorer editor emits and every runtime accepts it. Both pass the checks.

**02 — Genie Code suggestions.** When an agent is created, Genie Code launches and proposes context.
Students who click "accept all" sometimes add tables, which fails `test_agent_is_tightly_scoped`.
The message explains why; let them remove the tables.

**02 — benchmarks vs example SQL.** Example SQL is shown to Genie as guidance; benchmarks are the
answer key used to score it. Students who put the benchmark only under SQL Queries fail the benchmark
check. Good moment to explain why you keep evaluation separate from hints.

**03 — the metric-view agent gets it wrong.** It happens, especially with active customers (Genie adds
its own date filter). That is a lesson, not a bug: the fix is in the instructions, and the check
message says so. Have them start a new chat after editing.

**03 — raw agent answers.** Expect different students to get different raw-agent answers to the same
question; it usually picks the legacy summary or the fan-out join. `observations.diagnose_revenue()`
names which. Collect a few on the whiteboard: the spread across the room is the point.

**04 — ontology latency.** Inferred snippets and certification changes are indexed asynchronously;
allow a few minutes and a new chat. If Genie One still prefers the legacy table, the description fix
plus the deprecation tag is usually enough.

---

## If Genie Ontology or Genie One is not enabled on the training account

- **Genie One missing entirely** (no `/one`, no app switcher): run 04 Steps 1 and 3 (curation is plain
  Unity Catalog and always checkable), and have students record `availability="unavailable"` for the
  inspect, action and answer steps with a note of what they saw. The checks pass on a recorded, explained
  unavailability. Demo Genie One from an instructor workspace if you have one.
- **Genie One present, no citations:** Genie Ontology is not on. Students record the answer and note
  "no citations". The answer check still compares the number.
- **Cannot edit agents from Genie One:** record the action as unavailable; demonstrate the same change
  through the UI or the Genie API (`PATCH /api/2.0/genie/spaces/{id}`).
- **No ASSIGN on the certification tag:** 3B (description) satisfies the curation check.

---

## Reuse from the FinOps lab

| Asset | Disposition |
|---|---|
| Folder layout (`notebooks/`, `helpers/`, `helpers/tests/`) | Same structure |
| `utils.py` (`get_param`, `get_catalog`, `get_base_user_schema`, `get_schema`, `fq`, `use_lab_schema`, `table_exists`, `query_scalar`, ...) | Carried over; `data_mode` removed (no real-data mode); added `fq_plain`, `workspace_url`, `to_float` and the metric-view constants. `DEFAULT_CATALOG` is again the single source of the catalog name. |
| `setup_schemas.py` | Same logic (reuse, create, exact GRANT on failure); added `print_instructor_grants()` so no doc needs the catalog literal |
| `test_runner.py` | Copied byte-for-byte |
| `lab_views.py` indirection (`lab_usage` pattern) | Same idea: every consumer, including metric views and Genie Agents, points at `lab_*` views |
| Seeded generator (`synthetic_billing.py`) | Same idea in `shop_data.py`; pure Python, Spark only to write, validated offline |
| `00-setup` / `99-cleanup` | Same shape; cleanup also trashes registered Genie Agents |
| `Makefile`, `build.py` | Copied unchanged |
| New | `ground_truth.py` (expected values independent of the metric view), `genie_agents.py` (Genie REST), `observations.py` (recording UI evidence), `ontology.py` (curation) |

---

## Extending this lab

1. **Window measures.** Replace the point-in-time `active_customers` with a `trailing 90 day` window
   measure so it can be trended by month.
2. **Materialization.** Add a `materialization` block and compare query profiles.
3. **Agent CI.** Put the Exercise 2 agent in a bundle (`genie_spaces`) and run its benchmarks in a job
   on every change to the metric view.
