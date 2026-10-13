"""
Checks for 03-genie-vs-raw-tables.

Genie's chat answers live in the UI, so these checks work on what you recorded in
`genie_observations`, and verify it where possible: the SQL you pasted is re-run against the data
and must produce the number you recorded.
"""

from helpers import genie_agents, ground_truth, observations, utils

spark = utils.spark
EX, STEP = "03", "compare"
ROLES = ("metric_view_agent", "raw_tables_agent")


def _obs(role: str, key: str):
    row = observations.get(EX, STEP, role, key)
    assert row is not None, (f"Nothing recorded for {role} / {key}. Ask that agent "
                             f"\"{observations.QUESTIONS[key]}\" and record it in Step 2.")
    return row


def _first_number(sql: str):
    row = spark.sql(sql.strip().rstrip(";")).collect()[0]
    for v in row:
        if (isinstance(v, (int, float)) and not isinstance(v, bool)) or hasattr(v, "as_tuple"):
            return float(v)
    return None


def test_raw_agent_registered_and_raw_only(**kwargs):
    sid = genie_agents.registered_id("raw_tables_agent")
    assert sid, "Register your raw-tables agent in Step 1 (genie_agents.register('raw_tables_agent', ...))."
    ds = genie_agents.data_sources(genie_agents.config(sid))
    assert not ds["metric_views"] and not any(utils.METRIC_VIEW in t for t in ds["tables"]), (
        f"The raw-tables agent must not see the metric view; it has {ds}. The comparison only means something "
        f"if this agent has to work from raw tables.")
    assert len(ds["tables"]) >= 3, f"Give the raw agent the raw views listed in Step 1; it has {ds['tables']}."


def test_both_agents_answered_both_questions(**kwargs):
    for role in ROLES:
        for key in ("revenue_90d", "active_customers"):
            row = _obs(role, key)
            assert row.answer_value is not None and row.generated_sql, (
                f"{role} / {key}: record both the number and the SQL Genie generated (Show code / View SQL).")


def test_metric_view_agent_sql_uses_the_metric_view(**kwargs):
    sql = _obs("metric_view_agent", "revenue_90d").generated_sql.lower()
    assert utils.METRIC_VIEW in sql and "measure(" in sql, (
        "The SQL recorded for the metric-view agent does not query the metric view with MEASURE(). "
        "Did you paste the raw agent's SQL by mistake?")


def test_metric_view_agent_sql_reproduces_recorded_value(**kwargs):
    row = _obs("metric_view_agent", "revenue_90d")
    try:
        rerun = _first_number(row.generated_sql)
    except Exception as exc:
        raise AssertionError(f"The recorded SQL does not run here: {str(exc).splitlines()[0][:200]}") from None
    assert ground_truth.close(rerun, row.answer_value), (
        f"Re-running the recorded SQL gives {rerun}, but you recorded {row.answer_value}. Record the number "
        f"Genie showed for exactly that SQL.")


def test_metric_view_agent_revenue_is_governed(**kwargs):
    value, expected = _obs("metric_view_agent", "revenue_90d").answer_value, ground_truth.net_revenue(90)
    assert ground_truth.close(value, expected), (
        f"Your metric-view agent answered {value:,.2f}; governed net revenue is {expected:,.2f}. Run "
        f"observations.diagnose_revenue() to see which definition it used, tighten its instructions, "
        f"start a NEW chat and ask again.")


def test_metric_view_agent_active_customers_is_governed(**kwargs):
    value, expected = _obs("metric_view_agent", "active_customers").answer_value, ground_truth.active_customers(90)
    assert value is not None and int(round(value)) == expected, (
        f"Your metric-view agent answered {value}; the governed active-customer count is {expected}. "
        f"Genie probably added its own date filter on top of the measure; the instructions say not to.")


def test_raw_agent_sql_does_not_use_the_metric_view(**kwargs):
    sql = _obs("raw_tables_agent", "revenue_90d").generated_sql.lower()
    assert utils.METRIC_VIEW not in sql, "The raw agent's recorded SQL references the metric view; roles swapped?"


# ----------------------------------------------------------------- Challenge 3

def test_challenge_recommendation(**kwargs):
    try:
        rec = spark.sql(f"SELECT * FROM {utils.fq(observations.RECOMMENDATION)}").collect()
    except Exception:
        rec = []
    assert rec, "Challenge 3: save your recommendation with observations.save_recommendation(...)."
    rec = rec[0]
    assert rec.winner == "metric_view_agent", (
        f"winner = {rec.winner!r}. Which agent's revenue matched the governed number? Name its role.")
    assert len(rec.rationale) >= 60, "Give a rationale of at least a couple of sentences, grounded in what you saw."
    assert len(rec.raw_agent_fix) >= 20, "Name one concrete change that would make the raw agent less wrong."
