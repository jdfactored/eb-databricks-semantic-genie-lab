"""
Genie Agents (formerly Genie Spaces) through the REST API.

Genie Agents are created in the UI in this lab, but their configuration is a real Databricks
object you can read back:  GET /api/2.0/genie/spaces/{id}?include_serialized_space=true
returns the data sources, instructions, example SQL and benchmarks as JSON (you need CAN EDIT,
which the creator has). That is what the checks inspect.

The REST paths are called through the SDK's authenticated `api_client` rather than typed SDK
methods, so the helpers keep working across SDK versions while the API stays the same.
"""

import json
import time
from typing import Dict, List, Optional

from helpers import utils

spark = utils.spark
REGISTRY = "genie_agent_registry"
ROLES = ("metric_view_agent", "raw_tables_agent", "mixed_clone_agent")
API = "/api/2.0/genie/spaces"


def _do(method: str, path: str, query: Optional[Dict] = None, body: Optional[Dict] = None) -> Dict:
    return utils.workspace.api_client.do(method, path, query=query, body=body) or {}


# --------------------------------------------------------------------------- preparation

def find_warehouses() -> List[Dict]:
    """SQL warehouses you can see, serverless first. Genie needs a pro or serverless warehouse."""
    out = []
    try:
        for wh in utils.workspace.warehouses.list():
            kind = "serverless" if getattr(wh, "enable_serverless_compute", False) else \
                (str(getattr(wh, "warehouse_type", "")) or "unknown").split(".")[-1].lower()
            out.append({"id": wh.id, "name": wh.name, "type": kind,
                        "state": str(getattr(wh, "state", "")).split(".")[-1]})
    except Exception as exc:
        print(f"Could not list SQL warehouses ({type(exc).__name__}). Ask your instructor which one to use.")
    return sorted(out, key=lambda w: (w["type"] != "serverless", w["name"]))


def suggested_title(role: str) -> str:
    label = {"metric_view_agent": "Lumen Revenue (metric view)",
             "raw_tables_agent": "Lumen Revenue (raw tables)",
             "mixed_clone_agent": "Lumen Revenue (mixed clone)"}[role]
    return f"{utils.get_base_user_schema()} - {label}"


def agent_kit() -> Dict[str, str]:
    """Everything Exercise 2 pastes into the Genie Agent UI, with your fully-qualified names."""
    mv, targets = utils.fq_plain(utils.METRIC_VIEW), utils.fq_plain("lab_region_targets")
    return {
        "title": suggested_title("metric_view_agent"),
        "description": "Governed revenue, order and customer questions for Lumen Outfitters.",
        "instructions": (
            f"Lumen Outfitters sales questions. Use the metric view {mv} for every revenue, order and customer question.\n"
            f"- 'Revenue', 'sales' or 'turnover' always means the net_revenue measure (net of refunds, excluding "
            f"cancelled and test orders). Use gross_revenue only when the user explicitly asks for gross bookings or GMV.\n"
            f"- 'Active customers' means the active_customers measure. It already covers the trailing 90 days; "
            f"never add another date filter to it.\n"
            f"- 'Last N days' means order_date >= current_date() - INTERVAL N DAYS. The data ends yesterday.\n"
            f"- {targets} holds 90-day net revenue targets, one row per region. Compare them with net_revenue for "
            f"the last 90 days: aggregate the metric view in a CTE, then join on region (metric views cannot be "
            f"joined directly).\n"
            f"- Round money to 2 decimals and call it 'net revenue' in the answer."),
        "example_question": "Net revenue by region for the last 90 days",
        "example_sql": (f"SELECT region, MEASURE(net_revenue) AS net_revenue\nFROM {mv}\n"
                        f"WHERE order_date >= current_date() - INTERVAL 90 DAYS\nGROUP BY region\n"
                        f"ORDER BY net_revenue DESC"),
        "benchmark_question": "What was our revenue in the last 90 days?",
        "benchmark_sql": (f"SELECT MEASURE(net_revenue) AS net_revenue\nFROM {mv}\n"
                          f"WHERE order_date >= current_date() - INTERVAL 90 DAYS"),
    }


def print_agent_kit() -> None:
    kit = agent_kit()
    for label, key in [("TITLE", "title"), ("DESCRIPTION", "description"), ("TEXT INSTRUCTIONS", "instructions"),
                       ("EXAMPLE SQL - question", "example_question"), ("EXAMPLE SQL - query", "example_sql"),
                       ("BENCHMARK - question", "benchmark_question"), ("BENCHMARK - SQL answer", "benchmark_sql")]:
        print(f"===== {label} =====\n{kit[key]}\n")


def registered_agents() -> List[Dict]:
    try:
        return [r.asDict() for r in spark.sql(f"SELECT role, space_id, title FROM {utils.fq(REGISTRY)}").collect()]
    except Exception:
        return []


# --------------------------------------------------------------------------- registry

def _ensure_registry() -> None:
    spark.sql(f"CREATE TABLE IF NOT EXISTS {utils.fq(REGISTRY)} "
              f"(role STRING, space_id STRING, title STRING, registered_at TIMESTAMP)")


def list_my_agents(title_contains: Optional[str] = None) -> List[Dict]:
    """Genie Agents visible to you, optionally filtered by title (case-insensitive)."""
    agents, token = [], None
    for _ in range(20):
        resp = _do("GET", API, query={"page_size": 100, **({"page_token": token} if token else {})})
        agents += resp.get("spaces", [])
        token = resp.get("next_page_token")
        if not token:
            break
    if title_contains:
        agents = [a for a in agents if title_contains.lower() in (a.get("title") or "").lower()]
    return agents


def register(role: str, space_id: str = "") -> str:
    """
    Remember which Genie Agent plays which role so checks and cleanup can find it.
    Leave space_id empty to auto-discover by the suggested title.
    """
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    space_id = (space_id or "").strip()
    if not space_id:
        matches = list_my_agents(suggested_title(role))
        if len(matches) != 1:
            names = [m.get("title") for m in matches]
            raise ValueError(
                f"Could not auto-discover the '{role}' agent: {len(matches)} agents are titled like "
                f"'{suggested_title(role)}' {names}. Paste its ID instead: it is the 32-character "
                f"hex string in the agent's URL.")
        space_id = matches[0]["space_id"]
    space = get_space(space_id)
    _ensure_registry()
    spark.sql(f"DELETE FROM {utils.fq(REGISTRY)} WHERE role = '{role}'")
    (spark.createDataFrame([(role, space_id, space.get("title", ""))], "role STRING, space_id STRING, title STRING")
     .selectExpr("*", "current_timestamp() AS registered_at")
     .write.mode("append").saveAsTable(utils.fq(REGISTRY)))
    print(f"Registered '{space.get('title')}' as {role} ({space_id}).")
    return space_id


def registered_id(role: str) -> Optional[str]:
    try:
        return utils.query_scalar(f"SELECT space_id FROM {utils.fq(REGISTRY)} WHERE role = '{role}' "
                                  f"ORDER BY registered_at DESC LIMIT 1")
    except Exception:
        return None


# --------------------------------------------------------------------------- inspection

def get_space(space_id: str) -> Dict:
    return _do("GET", f"{API}/{space_id}", query={"include_serialized_space": "true"})


def config(space_id: str) -> Dict:
    """The parsed serialized_space: data_sources, instructions, benchmarks, config."""
    raw = get_space(space_id).get("serialized_space") or "{}"
    return json.loads(raw) if isinstance(raw, str) else raw


def _joined(value) -> str:
    return "".join(value) if isinstance(value, list) else (value or "")


def data_sources(cfg: Dict) -> Dict[str, List[str]]:
    ds = cfg.get("data_sources") or {}
    return {
        "tables": [t.get("identifier", "").lower() for t in ds.get("tables", [])],
        "metric_views": [m.get("identifier", "").lower() for m in ds.get("metric_views", [])],
    }


def text_instructions(cfg: Dict) -> str:
    return "\n".join(_joined(t.get("content")) for t in (cfg.get("instructions") or {}).get("text_instructions", []))


def example_sqls(cfg: Dict) -> List[Dict]:
    return [{"question": _joined(e.get("question")), "sql": _joined(e.get("sql"))}
            for e in (cfg.get("instructions") or {}).get("example_question_sqls", [])]


def benchmarks(cfg: Dict) -> List[Dict]:
    out = []
    for q in (cfg.get("benchmarks") or {}).get("questions", []):
        answers = q.get("answer") or []
        sql = _joined(answers[0].get("content")) if answers else ""
        out.append({"question": _joined(q.get("question")), "sql": sql})
    return out


def describe(space_id: str) -> None:
    space = get_space(space_id)
    cfg = config(space_id)
    ds = data_sources(cfg)
    print(f"Title:          {space.get('title')}")
    print(f"Warehouse:      {space.get('warehouse_id') or '(none)'}")
    print(f"Metric views:   {ds['metric_views'] or '-'}")
    print(f"Tables/views:   {ds['tables'] or '-'}")
    ti = text_instructions(cfg)
    print(f"Instructions:   {len(ti)} characters" + (f"\n  {ti[:300]}{'...' if len(ti) > 300 else ''}" if ti else ""))
    for e in example_sqls(cfg):
        print(f"Example SQL:    {e['question']}")
    for b in benchmarks(cfg):
        print(f"Benchmark:      {b['question']}")


# --------------------------------------------------------------------------- conversation API

def ask(space_id: str, question: str, timeout_s: int = 180) -> Dict:
    """
    Ask a Genie Agent a question through the Conversation API and return
    {"status", "sql", "description", "first_value", "rows"}. Optional: the UI is the main path.
    """
    start = _do("POST", f"{API}/{space_id}/start-conversation", body={"content": question})
    conv = start.get("conversation_id") or (start.get("conversation") or {}).get("id")
    msg = start.get("message_id") or (start.get("message") or {}).get("id")
    path = f"{API}/{space_id}/conversations/{conv}/messages/{msg}"
    deadline, delay, message = time.time() + timeout_s, 2, {}
    while time.time() < deadline:
        message = _do("GET", path)
        if message.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"):
            break
        time.sleep(delay)
        delay = min(delay * 1.5, 10)
    result = {"status": message.get("status", "TIMEOUT"), "sql": None, "description": None,
              "first_value": None, "rows": []}
    for att in message.get("attachments") or []:
        query = att.get("query")
        if not query:
            continue
        result["sql"], result["description"] = query.get("query"), query.get("description")
        try:
            data = _do("GET", f"{path}/attachments/{att['attachment_id']}/query-result")
            rows = ((data.get("statement_response") or {}).get("result") or {}).get("data_array") or []
            result["rows"] = rows[:20]
            numeric = [v for v in (rows[0] if rows else []) if _is_number(v)]
            result["first_value"] = float(numeric[0]) if numeric else None
        except Exception as exc:
            result["description"] = f"{result['description']} (result fetch failed: {type(exc).__name__})"
        break
    return result


def _is_number(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- as code

def export_bundle(space_id: str, resource_key: str = "lumen_revenue_agent") -> None:
    """Print a Declarative Automation Bundles (formerly Asset Bundles) definition of a live agent."""
    space = get_space(space_id)
    cfg = config(space_id)
    print("# databricks.yml  (requires Databricks CLI 1.3.0+ and the direct deployment engine)")
    print(f"""bundle:
  name: lumen-genie
  engine: direct

resources:
  genie_spaces:
    {resource_key}:
      title: '{space.get("title", "")}'
      description: 'Governed revenue questions for Lumen Outfitters'
      warehouse_id: ${{var.warehouse_id}}
      file_path: ./{resource_key}.geniespace.json
      permissions:
        - level: CAN_RUN
          group_name: users

variables:
  warehouse_id:
    default: {space.get("warehouse_id", "<warehouse-id>")}
""")
    print(f"# {resource_key}.geniespace.json  (exported from your live agent)")
    print(json.dumps(cfg, indent=2)[:6000])


def trash(space_id: str) -> None:
    _do("DELETE", f"{API}/{space_id}")
