"""
Checks for 02-genie-agents.

What is checked comes from the Genie API (the agent's serialized configuration) and from running
the agent's own benchmark SQL against the data. What cannot be checked, such as whether an
instruction is well written, is reviewed by the instructor, not faked here.
"""

from helpers import genie_agents, ground_truth, semantic_model, utils

spark = utils.spark
ROLE = "metric_view_agent"
FACT_VIEWS = ("lab_orders", "lab_refunds", "lab_customers", "lab_products", "lab_daily_sales_summary",
              "order_refund_totals", "synthetic_")


def _agent():
    sid = genie_agents.registered_id(ROLE)
    assert sid, (f"No Genie Agent registered as '{ROLE}'. Run the register cell in Step 3 "
                 f"(genie_agents.register('{ROLE}', AGENT_ID)).")
    try:
        return sid, genie_agents.get_space(sid), genie_agents.config(sid)
    except Exception as exc:
        raise AssertionError(f"Could not read Genie Agent {sid} via the API ({type(exc).__name__}: "
                             f"{str(exc)[:150]}). You need CAN EDIT on it; the creator has it.") from None


def _first_row(sql: str):
    return spark.sql(sql.strip().rstrip(";")).collect()[0]


def _mv_name() -> str:
    return utils.fq_plain(utils.METRIC_VIEW).lower()


def test_metric_view_still_exists(**kwargs):
    assert semantic_model.get_definition(), f"Metric view `{utils.METRIC_VIEW}` is missing. Finish 01 first."


def test_agent_registered_and_readable(**kwargs):
    _agent()


def test_agent_has_a_warehouse(**kwargs):
    _, space, _ = _agent()
    assert space.get("warehouse_id"), "Pick a SQL warehouse in the agent's Settings; Genie runs its SQL there."


def test_agent_uses_your_metric_view(**kwargs):
    _, _, cfg = _agent()
    ds = genie_agents.data_sources(cfg)
    assert _mv_name() in ds["metric_views"] + ds["tables"], (
        f"The agent's data sources are {ds}. Add your metric view {utils.fq_plain(utils.METRIC_VIEW)}.")


def test_agent_is_tightly_scoped(**kwargs):
    _, _, cfg = _agent()
    ds = genie_agents.data_sources(cfg)
    sources = ds["metric_views"] + ds["tables"]
    facts = [s for s in sources if any(s.split(".")[-1].startswith(f) for f in FACT_VIEWS)]
    assert not facts, (
        f"The agent also has raw fact/dimension views {facts}. Next to a metric view they invite Genie to "
        f"re-derive revenue from raw rows (and to join refunds at the wrong grain). Remove them; Exercise 3 "
        f"shows what happens when you don't.")
    assert len(sources) <= 3, f"{len(sources)} data sources. Keep this agent to the metric view plus a lookup."


def test_agent_has_text_instructions(**kwargs):
    _, _, cfg = _agent()
    text = genie_agents.text_instructions(cfg)
    assert len(text.strip()) >= 40 and "revenue" in text.lower(), (
        "Add the text instructions from Step 1 (Configure > Instructions > Text). They must at least say "
        "what 'revenue' means. Whether they are GOOD instructions is reviewed by your instructor.")


def test_agent_has_example_sql_on_metric_view(**kwargs):
    _, _, cfg = _agent()
    examples = genie_agents.example_sqls(cfg)
    on_mv = [e for e in examples if utils.METRIC_VIEW in e["sql"].lower() and "measure(" in e["sql"].lower()]
    assert on_mv, (f"Found {len(examples)} example SQL queries, none querying {utils.METRIC_VIEW} with "
                   f"MEASURE(). Add the example from Step 1.")


def test_revenue_benchmark_returns_the_governed_number(**kwargs):
    _, _, cfg = _agent()
    marks = [b for b in genie_agents.benchmarks(cfg)
             if "revenue" in b["question"].lower() and "target" not in b["question"].lower()]
    assert marks, "Add the revenue benchmark from Step 1 (question plus its correct SQL)."
    expected = ground_truth.net_revenue(90)
    row = _first_row(marks[0]["sql"])
    values = [float(v) for v in row if isinstance(v, (int, float)) or hasattr(v, "as_tuple")]
    assert values and ground_truth.close(values[0], expected), (
        f"Benchmark '{marks[0]['question']}' returns {values[:1]}; net revenue for the last 90 days is "
        f"{expected:,.2f}. A benchmark's SQL is the answer key, so it has to be right.")


# ----------------------------------------------------------------- Challenge 2

def test_challenge_target_benchmark(**kwargs):
    _, _, cfg = _agent()
    marks = [b for b in genie_agents.benchmarks(cfg) if "target" in b["question"].lower()]
    assert marks, "Challenge 2: add a benchmark whose question mentions 'target'."
    expected = ground_truth.region_furthest_below_target(90)
    try:
        row = _first_row(marks[0]["sql"])
    except Exception as exc:
        raise AssertionError(f"The target benchmark's SQL fails: {str(exc).splitlines()[0][:200]}") from None
    assert expected in [str(v) for v in row], (
        f"The first row of your target benchmark is {list(row)}; the region furthest below its 90-day target "
        f"is {expected}. Order by the gap ascending (or the percentage gap) and keep the region column.")
