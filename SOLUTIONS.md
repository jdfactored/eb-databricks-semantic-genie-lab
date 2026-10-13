# Reference Solutions — Instructor Copy

Keep this off the student branch.

Reference answers, not the only correct ones. The checks are behavioural: they look at the objects
and recorded evidence a student produced, not at how they produced them. Numbers quoted are for the
default seed on the day setup runs (see `INSTRUCTOR.md`).

---

## 01 — Semantic Layer and Metric Views

### Challenge 1 — `order_month` and `refund_rate`

```python
extra_dimensions = """
- name: order_month
  expr: DATE_TRUNC('MONTH', order_date)
  comment: "Calendar month of the order date."
  display_name: Order Month
  synonyms: ['month']
"""

extra_measures = """
- name: refund_rate
  expr: SUM(COALESCE(refunds.refund_amount, 0)) FILTER (WHERE status <> 'cancelled') / SUM(order_total) FILTER (WHERE status <> 'cancelled')
  comment: "Share of gross bookings refunded. Ratio between 0 and 1."
  display_name: Refund Rate
  synonyms: ['return rate', 'refund percentage']
"""

semantic_model.create_metric_view(extra_dimensions=extra_dimensions, extra_measures=extra_measures)
```

Expected: `refund_rate` all-time ≈ 0.0613. Equivalent: `1 - net/gross` written with the same two
aggregates. Common failures the checks catch:

- `* 100`: the message points out it looks like a percentage.
- Joining `lab_refunds` instead of using the `refunds` join: impossible here because the join is
  defined in the YAML, but students who rebuild the YAML by hand sometimes re-point it, and the
  rollup check plus the value check catch it.
- Leaving out the `FILTER`: cancelled orders inflate the denominator and the value check fails.

Discussion: `refund_rate` is a **ratio of sums**, so it re-aggregates correctly by any dimension.
Averaging per-order refund percentages would not, and is a good "why measures, not columns" example.

---

## 02 — Genie Agents

The Step 1 kit (`genie_agents.print_agent_kit()`) is the reference configuration for the agent itself.

### Challenge 2 — "Which region is furthest below its 90-day revenue target?"

```sql
WITH actual AS (
  SELECT region, MEASURE(net_revenue) AS net_revenue_90d
  FROM <DEFAULT_CATALOG>.<you>_semantic.sales_metrics
  WHERE order_date >= current_date() - INTERVAL 90 DAYS
  GROUP BY region
)
SELECT a.region,
       ROUND(a.net_revenue_90d, 2)                          AS net_revenue_90d,
       t.net_revenue_target_90d,
       ROUND(a.net_revenue_90d - t.net_revenue_target_90d, 2) AS gap,
       ROUND((a.net_revenue_90d - t.net_revenue_target_90d) / t.net_revenue_target_90d * 100, 1) AS gap_pct
FROM actual a
JOIN <DEFAULT_CATALOG>.<you>_semantic.lab_region_targets t ON a.region = t.region
ORDER BY gap ASC
```

(`<DEFAULT_CATALOG>.<you>_semantic` is the student's own namespace; the notebook prints it.)

Expected first row: **APAC**, about −$180k / −22% against target. Ordering by `gap_pct` gives the same
answer; the targets were calibrated so the two readings cannot disagree.

Common failure: `FROM sales_metrics JOIN lab_region_targets ...` directly. Metric views cannot be
joined at query time; the CTE is the documented pattern, and it is also what the text instructions tell
Genie to do.

---

## 03 — Genie on Raw Tables vs. a Metric View

There is no single right raw-agent answer; that is the point. What students typically record:

| Agent | Revenue, last 90 days | Usually because |
|---|---|---|
| metric-view agent | $3,600,536 | `MEASURE(net_revenue)`, synonym `revenue` |
| raw agent, variant 1 | ~$4.0M | `SUM(revenue) FROM lab_daily_sales_summary` (also 3 days stale) |
| raw agent, variant 2 | ~$3.91M | `lab_orders JOIN lab_refunds` fan-out |
| raw agent, variant 3 | ~$3.95M | `SUM(order_total)`, no refunds, test orders included |

Active customers: metric-view agent 3,205; raw agent usually 3,248 (90 days, any order) or the count of
all customers.

### Challenge 3 — recommendation

```python
observations.save_recommendation(
    winner="metric_view_agent",
    rationale=("The metric-view agent returned 3,600,536, matching the governed net revenue, and its SQL "
               "was a single MEASURE(net_revenue) on sales_metrics. The raw agent summed the legacy "
               "summary table's revenue column, which includes cancelled and test orders and is 3 days "
               "stale, so it overstated revenue by about 11%."),
    raw_agent_fix=("Remove lab_daily_sales_summary from the agent and deprecate it, and give the agent the "
                   "metric view instead of raw facts."),
)
```

The check requires `winner="metric_view_agent"`, a rationale of at least ~60 characters and a fix of at
least ~20. Grade the content by hand: the best answers cite the specific SQL they saw. Acceptable
fixes include: deprecate or remove the summary table, add text instructions defining revenue, add a
join spec through an order-grain refund view, add example SQL, or replace the raw tables with the
metric view.

---

## 04 — Genie Ontology and Genie One

### Step 3 — curation (any one satisfies the check)

```python
ontology.set_certification(utils.METRIC_VIEW, "certified")      # needs ASSIGN on the governed tag
ontology.set_certification(ontology.LEGACY_VIEW, "deprecated")  # needs ASSIGN on the governed tag
ontology.annotate_legacy_summary()                              # no extra grant
```

Equivalent SQL for the tag: ``SET TAG ON TABLE <view> `system.certification_status` = `certified`;``

### Step 4 — the action

The student pastes the line printed by `ontology.genie_one_instruction(...)` into Genie One and
approves the change. The check looks for `(added by Genie One)` in the agent's text instructions via
the Genie API. Fallback when Genie One cannot edit agents in the workspace:

```python
observations.record("04", "genie_one_action", availability="unavailable",
                    notes="Genie One replied that it cannot modify agents in this workspace.")
```

### Challenge 4 — governed answer from Genie One

```python
observations.record("04", "genie_one_answer", question_key="revenue_90d",
    answer_value=3600536.24,
    sources_cited="jane_doe - Lumen Revenue (metric view) agent; sales_metrics (certified metric view)",
    availability="available",
    notes="First attempt cited lab_daily_sales_summary; after deprecating it, a new chat routed to my agent.")
```

The check accepts a value within 0.5% of governed net revenue, or a recorded, explained unavailability.
When the value matches another definition, the failure message names which one (via
`ground_truth.revenue_candidates`), which makes for a good debrief: the ontology was not wrong, it was
following the strongest signal it had, and curation changes the signals.
