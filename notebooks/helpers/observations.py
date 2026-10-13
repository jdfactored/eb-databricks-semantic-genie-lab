"""
Record what you observed in the Genie UI, so grading and the checks have evidence to look at.

Much of Exercises 3 and 4 happens in the UI, which nothing can query. Instead of pretending to
check it, you write down what you saw (the number, the SQL Genie generated, the sources it cited)
in `genie_observations`. The checks then verify what can be verified: that the SQL you pasted
really produces the number you recorded, and that the number matches the governed definition.
"""

from typing import Optional

from helpers import ground_truth, utils

spark = utils.spark
TABLE = "genie_observations"
RECOMMENDATION = "genie_recommendation"

QUESTIONS = {
    "revenue_90d": "What was our revenue in the last 90 days?",
    "active_customers": "How many active customers do we have?",
    "revenue_definition": "How does Lumen Outfitters define revenue?",
}

_SCHEMA = ("exercise STRING, step STRING, agent_role STRING, question_key STRING, answer_value DOUBLE, "
           "generated_sql STRING, sources_cited STRING, availability STRING, notes STRING")


def _q(value: Optional[str]) -> str:
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def record(exercise: str, step: str, agent_role: Optional[str] = None, question_key: Optional[str] = None,
           answer_value: Optional[float] = None, generated_sql: str = "", sources_cited: str = "",
           availability: str = "available", notes: str = "") -> None:
    """Insert or replace one observation, keyed by (exercise, step, agent_role, question_key)."""
    if availability not in ("available", "unavailable"):
        raise ValueError("availability must be 'available' or 'unavailable'")
    if question_key is not None and question_key not in QUESTIONS:
        raise ValueError(f"question_key must be one of {list(QUESTIONS)}")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {utils.fq(TABLE)} ({_SCHEMA}, recorded_at TIMESTAMP)")
    spark.sql(f"""DELETE FROM {utils.fq(TABLE)} WHERE exercise = {_q(exercise)} AND step = {_q(step)}
                  AND agent_role <=> {_q(agent_role)} AND question_key <=> {_q(question_key)}""")
    value = None if answer_value is None else float(answer_value)
    (spark.createDataFrame([(exercise, step, agent_role, question_key, value, (generated_sql or "").strip(),
                             sources_cited.strip(), availability, notes.strip())], _SCHEMA)
     .selectExpr("*", "current_timestamp() AS recorded_at")
     .write.mode("append").saveAsTable(utils.fq(TABLE)))
    shown = f"{value:,.2f}" if value is not None else "-"
    print(f"Recorded {exercise}/{step} {agent_role or ''} {question_key or ''} -> {shown} ({availability})")


def show(exercise: Optional[str] = None):
    where = f"WHERE exercise = {_q(exercise)}" if exercise else ""
    return spark.sql(f"SELECT exercise, step, agent_role, question_key, answer_value, availability, "
                     f"sources_cited, notes FROM {utils.fq(TABLE)} {where} ORDER BY recorded_at")


def get(exercise: str, step: str, agent_role: Optional[str] = None, question_key: Optional[str] = None):
    try:
        rows = spark.sql(f"""SELECT * FROM {utils.fq(TABLE)} WHERE exercise = {_q(exercise)} AND step = {_q(step)}
                             AND agent_role <=> {_q(agent_role)} AND question_key <=> {_q(question_key)}
                             ORDER BY recorded_at DESC LIMIT 1""").collect()
    except Exception:
        return None
    return rows[0] if rows else None


def diagnose_revenue(exercise: str = "03") -> None:
    """Say what each recorded 'revenue' number really is."""
    candidates = ground_truth.revenue_candidates(90)
    print("Known answers to 'revenue in the last 90 days', computed from the data:\n")
    for label, value in candidates.items():
        print(f"  {value:>16,.2f}  {label}")
    rows = spark.sql(f"SELECT agent_role, answer_value FROM {utils.fq(TABLE)} WHERE exercise = {_q(exercise)} "
                     f"AND question_key = 'revenue_90d' ORDER BY agent_role").collect()
    if not rows:
        print("\nNothing recorded yet for the revenue question.")
        return
    print("\nWhat your agents said:\n")
    for r in rows:
        match = next((label for label, v in candidates.items() if ground_truth.close(r.answer_value, v)), None)
        verdict = match or "none of the known definitions; look at its SQL"
        print(f"  {r.agent_role:20s} {r.answer_value or 0:>16,.2f}  -> {verdict}")


def save_recommendation(winner: str, rationale: str, raw_agent_fix: str) -> None:
    spark.sql(f"CREATE TABLE IF NOT EXISTS {utils.fq(RECOMMENDATION)} "
              f"(winner STRING, rationale STRING, raw_agent_fix STRING, saved_at TIMESTAMP)")
    spark.sql(f"DELETE FROM {utils.fq(RECOMMENDATION)}")
    (spark.createDataFrame([(winner.strip(), rationale.strip(), raw_agent_fix.strip())],
                           "winner STRING, rationale STRING, raw_agent_fix STRING")
     .selectExpr("*", "current_timestamp() AS saved_at")
     .write.mode("append").saveAsTable(utils.fq(RECOMMENDATION)))
    print("Saved your recommendation.")
