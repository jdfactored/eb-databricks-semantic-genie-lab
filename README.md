[template-version]: # (0.0.2)
# Semantic Layer & Genie on Databricks Lab

**Tools**: Databricks, Unity Catalog metric views, Genie Agents, Genie Ontology, Genie One, Databricks SDK
**Time**: 45–60 minutes of hands-on work
**Compute**: Serverless for the notebooks, plus a pro or serverless SQL warehouse for Genie
**Prerequisite**: working SQL and basic PySpark. No Genie experience needed.

---

## What this lab is

You own the semantic layer at *Lumen Outfitters*, an outdoor-gear web shop. Two analysts just gave
the CFO two different revenue numbers, Marketing and Customer Success disagree on how many active
customers there are, and the business wants to ask an AI assistant instead. Your job: define the
metrics once, put a Genie Agent on top, prove that it beats an agent on raw tables, and make the
governed definition the one Genie One reaches for.

The data is synthetic and seeded, so the lab works on a brand-new workspace and everyone gets the
same numbers.

## Notebooks

```
notebooks/
  00-setup.ipynb                          run once, no code required               3 min

  01-semantic-layer-and-metric-views.ipynb  ambiguous metrics, metric view YAML   15 min
  02-genie-agents.ipynb                   build and configure a Genie Agent       12 min
  03-genie-vs-raw-tables.ipynb            same question, two agents; agent-as-code 12 min
  04-genie-ontology-and-genie-one.ipynb   curate context, ask and act in Genie One 13 min

  99-cleanup.ipynb                        run only after grading                   1 min
```

Exercises 2–4 are partly done in the Databricks UI. The notebooks give numbered steps, prepare
everything you need to paste, and record what you observed.

## Getting started

1. In your workspace, **Workspace > Create > Git folder**, and paste this repository's URL.
2. Attach `00-setup.ipynb` to **Serverless** and run it top to bottom.
3. Work through `01` to `04` in order. Each depends on the one before.

Each notebook explains a concept, runs worked steps, then ends with a **Challenge** and a **TO DO**
cell. `%sql` cells are fine wherever you prefer them.

## Your workspace

Everything you create in Unity Catalog lives in one schema, named from `current_user()`.

| Object | Name |
|---|---|
| Schema | `<DEFAULT_CATALOG>.<you>_semantic` (`DEFAULT_CATALOG` is set in `helpers/utils.py`; `00-setup` prints the real name) |
| Synthetic tables | `synthetic_customers`, `synthetic_products`, `synthetic_orders`, `synthetic_refunds`, `synthetic_daily_sales_summary` |
| Lab views (what you query) | `lab_customers`, `lab_products`, `lab_orders`, `lab_refunds`, `lab_daily_sales_summary`, `lab_region_targets` |
| Reference tables | `region_targets`, `metric_glossary` |
| Built by you | `order_refund_totals`, `sales_metrics` (metric view), `metric_reconciliation`, `genie_agent_registry`, `genie_observations`, `genie_recommendation` |
| Genie Agents | `<you> - Lumen Revenue (metric view)`, `<you> - Lumen Revenue (raw tables)` in your user folder |

Every exercise notebook starts with `utils.use_lab_schema()`, so `%sql` cells can use unqualified
names such as `lab_orders`. If a `%sql` cell says a table does not exist, re-run that first cell.

## How checks work

The last cell of each notebook runs its checks:

```python
from helpers import test_runner
test_runner.run("01-semantic-layer-and-metric-views")
```

Each check prints PASS or FAIL with a message that explains what to change. Expected values are
always computed from the data at check time, never hardcoded, and never from your own metric view.

For the UI parts, the checks read your Genie Agents' configuration through the Genie API and
**execute** their benchmark SQL against the data. Where a step cannot be checked (whether an
instruction is well written, what Genie One showed you), you record what you saw in
`genie_observations`; the checks verify what can be verified, such as re-running the SQL you pasted.

Some Genie features depend on account settings (Genie Ontology is in Public Preview). If a feature is
not available to you, the notebook tells you to record `availability="unavailable"` with a note. That
counts; skipping the step silently does not.

## Cleanup

`99-cleanup.ipynb` drops your schema and trashes the Genie Agents you registered. Run it only after
grading. Draft Pages and Genie One chats are removed by hand.
