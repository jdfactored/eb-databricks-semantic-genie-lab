"""
Everything Exercise 1 builds: the two pairs of "reasonable" raw queries, the order-grain refund
rollup, the `sales_metrics` metric view, and the reconciliation table that proves the fix.

The raw SQL is kept here as templates so that the `%sql` cells in the notebook and the
reconciliation that saves the numbers run exactly the same text.
"""

import json
import textwrap
from typing import Dict, List, Optional

from helpers import utils

spark = utils.spark

# --------------------------------------------------------------------------- raw queries

RAW_QUERIES = {
    # "What was our revenue in the last 90 days?"
    "raw_sales_ops": """\
-- Sales Ops dashboard: revenue = what customers paid, minus cancellations
SELECT ROUND(SUM(order_total), 2) AS revenue_90d
FROM {lab_orders}
WHERE status <> 'cancelled'
  AND order_date >= current_date() - INTERVAL 90 DAYS""",
    "raw_finance": """\
-- Finance notebook: revenue = order totals net of refunds
SELECT ROUND(SUM(o.order_total) - SUM(COALESCE(r.refund_amount, 0)), 2) AS revenue_90d
FROM {lab_orders} o
LEFT JOIN {lab_refunds} r ON o.order_id = r.order_id
WHERE o.status <> 'cancelled'
  AND o.order_date >= current_date() - INTERVAL 90 DAYS""",
    # "How many active customers do we have?"
    "raw_marketing_30d": """\
-- Marketing: active = ordered in the last 30 days
SELECT COUNT(DISTINCT customer_id) AS active_customers
FROM {lab_orders}
WHERE order_date >= current_date() - INTERVAL 30 DAYS""",
    "raw_cs_90d": """\
-- Customer Success: active = ordered in the last 90 days
SELECT COUNT(DISTINCT customer_id) AS active_customers
FROM {lab_orders}
WHERE order_date >= current_date() - INTERVAL 90 DAYS""",
}

FANOUT_EVIDENCE = """\
-- How many orders have more than one refund event? Each one is duplicated by the Finance join.
SELECT refund_events, COUNT(*) AS orders, ROUND(SUM(order_total), 2) AS order_total_duplicated
FROM (
  SELECT o.order_id, o.order_total, COUNT(r.refund_id) AS refund_events
  FROM {lab_orders} o JOIN {lab_refunds} r ON o.order_id = r.order_id
  GROUP BY o.order_id, o.order_total
)
GROUP BY refund_events
ORDER BY refund_events"""

TRAPS_EVIDENCE = """\
-- Two more things neither analyst filtered on
SELECT
  COUNT_IF(is_test_order)                                AS test_orders,
  ROUND(SUM(order_total) FILTER (WHERE is_test_order), 2) AS test_order_total,
  COUNT_IF(status = 'cancelled')                         AS cancelled_orders
FROM {lab_orders}
WHERE order_date >= current_date() - INTERVAL 90 DAYS"""

REFUND_ROLLUP = """\
CREATE OR REPLACE VIEW {order_refund_totals}
COMMENT 'Refunds rolled up to ONE ROW PER ORDER. Join this, never lab_refunds, to orders.'
AS SELECT
  order_id,
  SUM(refund_amount) AS refund_amount,
  COUNT(*)           AS refund_events
FROM {lab_refunds}
GROUP BY order_id"""


def _names(qualified: bool) -> Dict[str, str]:
    names = list(utils.LAB_VIEWS) + [utils.REFUND_ROLLUP_VIEW, utils.METRIC_VIEW]
    return {n: (utils.fq(n) if qualified else n) for n in names}


def render(template: str, qualified: bool = True) -> str:
    return template.format(**_names(qualified))


def raw_sql(key: str, qualified: bool = True) -> str:
    return render(RAW_QUERIES[key], qualified)


def create_refund_rollup() -> None:
    spark.sql(render(REFUND_ROLLUP))
    print(f"Created view: {utils.REFUND_ROLLUP_VIEW} (one row per refunded order)")


# --------------------------------------------------------------------------- metric view

_YAML = """\
version: 1.1
comment: "Governed sales KPIs for Lumen Outfitters. 'Revenue' means net_revenue: completed, non-test orders minus refunds, by order date. Owner: Finance."
source: {orders}
filter: NOT is_test_order

joins:
  - name: customer
    source: {customers}
    'on': source.customer_id = customer.customer_id
  - name: product
    source: {products}
    'on': source.product_id = product.product_id
  - name: refunds
    source: {refund_totals}
    'on': source.order_id = refunds.order_id

dimensions:
  - name: order_date
    expr: order_date
    comment: "Date the order was placed. Refunds are attributed to this date."
    display_name: Order Date
    synonyms: ['date', 'purchase date', 'day']
  - name: region
    expr: customer.region
    comment: "Customer sales region: NA, EMEA, APAC or LATAM."
    display_name: Region
    synonyms: ['market', 'geo', 'territory']
  - name: customer_segment
    expr: customer.segment
    comment: "consumer or smb."
    display_name: Customer Segment
    synonyms: ['segment']
  - name: product_category
    expr: product.category
    comment: "Footwear, Outerwear, Camping, Climbing or Accessories."
    display_name: Product Category
    synonyms: ['category', 'department', 'product line']
  - name: channel
    expr: channel
    comment: "Sales channel: web, app or marketplace."
    display_name: Channel
{extra_dimensions}
measures:
  - name: net_revenue
    expr: SUM(order_total - COALESCE(refunds.refund_amount, 0)) FILTER (WHERE status <> 'cancelled')
    comment: "THE company revenue figure. Completed orders minus every refund issued against them."
    display_name: Net Revenue
    synonyms: ['revenue', 'sales', 'net sales', 'turnover', 'income']
  - name: gross_revenue
    expr: SUM(order_total) FILTER (WHERE status <> 'cancelled')
    comment: "Gross bookings before refunds. Never report this as revenue."
    display_name: Gross Bookings
    synonyms: ['gross bookings', 'GMV', 'bookings', 'gross sales']
  - name: order_count
    expr: COUNT(DISTINCT order_id) FILTER (WHERE status <> 'cancelled')
    comment: "Number of completed orders."
    display_name: Orders
    synonyms: ['orders', 'number of orders', 'order volume']
  - name: active_customers
    expr: COUNT(DISTINCT customer_id) FILTER (WHERE status <> 'cancelled' AND order_date >= current_date() - INTERVAL 90 DAYS)
    comment: "Customers with a completed order in the trailing 90 days. Point-in-time KPI as of today; do not add another date filter."
    display_name: Active Customers
    synonyms: ['active users', 'active buyers', 'active accounts']
{extra_measures}"""


def _indent_block(block: str) -> str:
    block = textwrap.dedent(block or "").strip("\n")
    if not block.strip():
        return ""
    return "\n".join(("  " + line) if line.strip() else "" for line in block.splitlines()) + "\n"


def metric_view_yaml(extra_dimensions: str = "", extra_measures: str = "") -> str:
    return _YAML.format(
        orders=utils.fq_plain("lab_orders"), customers=utils.fq_plain("lab_customers"),
        products=utils.fq_plain("lab_products"), refund_totals=utils.fq_plain(utils.REFUND_ROLLUP_VIEW),
        extra_dimensions=_indent_block(extra_dimensions), extra_measures=_indent_block(extra_measures),
    )


def create_metric_view(extra_dimensions: str = "", extra_measures: str = "", show_yaml: bool = False) -> str:
    yaml_text = metric_view_yaml(extra_dimensions, extra_measures)
    if show_yaml:
        print(yaml_text)
    try:
        spark.sql(f"CREATE OR REPLACE VIEW {utils.fq(utils.METRIC_VIEW)}\n"
                  f"WITH METRICS\nLANGUAGE YAML\nAS $$\n{yaml_text}$$")
    except Exception as exc:
        numbered = "\n".join(f"{i:3d}  {line}" for i, line in enumerate(yaml_text.splitlines(), 1))
        first = str(exc).strip().splitlines()[0][:400]
        raise ValueError(f"The metric view was rejected:\n  {first}\n\nYAML that was submitted:\n{numbered}") from None
    summary = summarize()
    print(f"Created metric view: {utils.fq_plain(utils.METRIC_VIEW)}")
    print(f"  dimensions: {', '.join(summary['dimensions'])}")
    print(f"  measures:   {', '.join(summary['measures'])}")
    print(f"  joins:      {', '.join(summary['joins'])}")
    return yaml_text


# --------------------------------------------------------------------------- read it back

def get_definition(name: Optional[str] = None) -> Optional[str]:
    """The YAML stored in Unity Catalog ('View Text'), or None if the view does not exist."""
    name = name or utils.METRIC_VIEW
    try:
        raw = spark.sql(f"DESCRIBE TABLE EXTENDED {utils.fq(name)} AS JSON").collect()[0][0]
        info = json.loads(raw)
        text = info.get("view_text") or info.get("View Text")
        if text:
            return text
    except Exception:
        pass
    try:
        return utils.workspace.tables.get(utils.fq_plain(name)).view_definition
    except Exception:
        return None


def _minimal_yaml(text: str) -> Dict:
    """Fallback when PyYAML is unavailable: enough structure for the checks."""
    out: Dict = {}
    section, item = None, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, val = line.partition(":")
            section, item = key.strip(), None
            out[section] = val.strip() if val.strip() else []
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and isinstance(out.get(section), list):
            item = {}
            out[section].append(item)
            stripped = stripped[2:]
        if item is not None and ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            item[key.strip()] = val
    return out


def parse_definition(text: Optional[str] = None) -> Dict:
    text = text if text is not None else get_definition()
    if not text:
        return {}
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _minimal_yaml(text)


def summarize(defn: Optional[Dict] = None) -> Dict[str, List]:
    defn = defn if defn is not None else parse_definition()
    dims = defn.get("dimensions") or defn.get("fields") or []
    measures = defn.get("measures") or []
    joins = defn.get("joins") or []
    synonyms = {}
    for entry in list(dims) + list(measures):
        for syn in (entry.get("synonyms") or []):
            synonyms[str(syn).lower()] = entry.get("name")
    return {
        "dimensions": [d.get("name") for d in dims],
        "measures": [m.get("name") for m in measures],
        "joins": [j.get("name") for j in joins],
        "synonyms": synonyms,
        "has_filter": bool(defn.get("filter")),
    }


# --------------------------------------------------------------------------- reconciliation

MV_QUERIES = {
    "revenue_total": """\
SELECT MEASURE(net_revenue) AS revenue_90d
FROM {sales_metrics}
WHERE order_date >= current_date() - INTERVAL 90 DAYS""",
    "revenue_by_category": """\
-- Finance's breakdown, through the metric view: the refund join can no longer fan out
SELECT product_category, MEASURE(net_revenue) AS revenue_90d
FROM {sales_metrics}
WHERE order_date >= current_date() - INTERVAL 90 DAYS
GROUP BY product_category
ORDER BY revenue_90d DESC""",
    "active_total": """\
SELECT MEASURE(active_customers) AS active_customers
FROM {sales_metrics}""",
    "active_by_region": """\
SELECT region, MEASURE(active_customers) AS active_customers
FROM {sales_metrics}
GROUP BY region
ORDER BY active_customers DESC""",
}


def mv_sql(key: str, qualified: bool = True) -> str:
    return render(MV_QUERIES[key], qualified)


def _sum_of(sql: str, column: str) -> float:
    return utils.to_float(utils.query_scalar(f"SELECT SUM({column}) FROM ({sql})"))


def reconcile() -> None:
    """Run every approach to both questions and save the numbers to `metric_reconciliation`."""
    rows = [
        ("revenue_90d", "raw_sales_ops", utils.to_float(utils.query_scalar(raw_sql("raw_sales_ops"))), raw_sql("raw_sales_ops", False)),
        ("revenue_90d", "raw_finance", utils.to_float(utils.query_scalar(raw_sql("raw_finance"))), raw_sql("raw_finance", False)),
        ("revenue_90d", "metric_view_total", utils.to_float(utils.query_scalar(mv_sql("revenue_total"))), mv_sql("revenue_total", False)),
        ("revenue_90d", "metric_view_sum_of_categories", _sum_of(mv_sql("revenue_by_category"), "revenue_90d"), mv_sql("revenue_by_category", False)),
        ("active_customers", "raw_marketing_30d", utils.to_float(utils.query_scalar(raw_sql("raw_marketing_30d"))), raw_sql("raw_marketing_30d", False)),
        ("active_customers", "raw_cs_90d", utils.to_float(utils.query_scalar(raw_sql("raw_cs_90d"))), raw_sql("raw_cs_90d", False)),
        ("active_customers", "metric_view_total", utils.to_float(utils.query_scalar(mv_sql("active_total"))), mv_sql("active_total", False)),
        ("active_customers", "metric_view_sum_of_regions", _sum_of(mv_sql("active_by_region"), "active_customers"), mv_sql("active_by_region", False)),
    ]
    (spark.createDataFrame(rows, "question STRING, approach STRING, value DOUBLE, sql_text STRING")
     .selectExpr("*", "current_timestamp() AS computed_at")
     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(utils.fq("metric_reconciliation")))
    print("Saved metric_reconciliation:\n")
    for question, approach, value, _ in rows:
        print(f"  {question:18s} {approach:32s} {value:>16,.2f}")
