"""
Expected answers, computed from the data with plain SQL that does NOT use the metric view.

The checks and the Exercise 3 diagnosis use this module, never the metric view, so a mistake in
the metric view cannot make its own check pass. Every number is computed at check time from the
lab views; nothing is hardcoded.
"""

from typing import Dict

from helpers import utils


def _v(name: str) -> str:
    return utils.fq(name)


def _window(days: int, col: str = "o.order_date") -> str:
    return f"{col} >= current_date() - INTERVAL {int(days)} DAYS"


def net_revenue(days: int = 90) -> float:
    """Company definition: completed, non-test orders minus all their refunds, order-date basis."""
    return utils.to_float(utils.query_scalar(f"""
        WITH r AS (SELECT order_id, SUM(refund_amount) AS amt FROM {_v('lab_refunds')} GROUP BY order_id)
        SELECT SUM(o.order_total - COALESCE(r.amt, 0))
        FROM {_v('lab_orders')} o LEFT JOIN r ON o.order_id = r.order_id
        WHERE o.status <> 'cancelled' AND NOT o.is_test_order AND {_window(days)}"""))


def gross_revenue(days: int = 90) -> float:
    return utils.to_float(utils.query_scalar(f"""
        SELECT SUM(o.order_total) FROM {_v('lab_orders')} o
        WHERE o.status <> 'cancelled' AND NOT o.is_test_order AND {_window(days)}"""))


def raw_sales_ops_revenue(days: int = 90) -> float:
    """Gross incl. test orders: what Sales Ops' dashboard reports."""
    return utils.to_float(utils.query_scalar(f"""
        SELECT SUM(o.order_total) FROM {_v('lab_orders')} o
        WHERE o.status <> 'cancelled' AND {_window(days)}"""))


def raw_finance_fanout_revenue(days: int = 90) -> float:
    """orders LEFT JOIN refunds at refund grain: order totals duplicated."""
    return utils.to_float(utils.query_scalar(f"""
        SELECT SUM(o.order_total) - SUM(COALESCE(r.refund_amount, 0))
        FROM {_v('lab_orders')} o LEFT JOIN {_v('lab_refunds')} r ON o.order_id = r.order_id
        WHERE o.status <> 'cancelled' AND {_window(days)}"""))


def legacy_summary_revenue(days: int = 90) -> float:
    return utils.to_float(utils.query_scalar(f"""
        SELECT SUM(revenue) FROM {_v('lab_daily_sales_summary')}
        WHERE {_window(days, 'sales_date')}"""))


def active_customers(days: int = 90) -> int:
    return int(utils.query_scalar(f"""
        SELECT COUNT(DISTINCT o.customer_id) FROM {_v('lab_orders')} o
        WHERE o.status <> 'cancelled' AND NOT o.is_test_order AND {_window(days)}"""))


def raw_active_customers(days: int) -> int:
    """Any order at all in the window: how Marketing (30d) and CS (90d) count."""
    return int(utils.query_scalar(f"""
        SELECT COUNT(DISTINCT o.customer_id) FROM {_v('lab_orders')} o WHERE {_window(days)}"""))


def refund_rate_all_time() -> float:
    return utils.to_float(utils.query_scalar(f"""
        WITH r AS (SELECT order_id, SUM(refund_amount) AS amt FROM {_v('lab_refunds')} GROUP BY order_id)
        SELECT SUM(COALESCE(r.amt, 0)) / SUM(o.order_total)
        FROM {_v('lab_orders')} o LEFT JOIN r ON o.order_id = r.order_id
        WHERE o.status <> 'cancelled' AND NOT o.is_test_order"""))


def months_spanned() -> int:
    return int(utils.query_scalar(f"""
        SELECT COUNT(DISTINCT date_trunc('MONTH', order_date)) FROM {_v('lab_orders')}
        WHERE NOT is_test_order"""))


def region_furthest_below_target(days: int = 90) -> str:
    return utils.query_scalar(f"""
        WITH r AS (SELECT order_id, SUM(refund_amount) AS amt FROM {_v('lab_refunds')} GROUP BY order_id),
        actual AS (
          SELECT c.region, SUM(o.order_total - COALESCE(r.amt, 0)) AS net
          FROM {_v('lab_orders')} o
          JOIN {_v('lab_customers')} c ON o.customer_id = c.customer_id
          LEFT JOIN r ON o.order_id = r.order_id
          WHERE o.status <> 'cancelled' AND NOT o.is_test_order AND {_window(days)}
          GROUP BY c.region)
        SELECT a.region FROM actual a JOIN {_v('lab_region_targets')} t ON a.region = t.region
        ORDER BY (a.net - t.net_revenue_target_90d) / t.net_revenue_target_90d LIMIT 1""")


def revenue_candidates(days: int = 90) -> Dict[str, float]:
    """Every 'revenue' a reasonable person (or Genie) might produce, keyed by what it really is."""
    return {
        "net_revenue (correct)": net_revenue(days),
        "gross, excl. test (not 'revenue')": gross_revenue(days),
        "gross incl. test orders (Sales Ops query)": raw_sales_ops_revenue(days),
        "orders x refunds fan-out (Finance query)": raw_finance_fanout_revenue(days),
        "legacy daily_sales_summary.revenue": legacy_summary_revenue(days),
    }


def close(a, b, rel: float = 0.005) -> bool:
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    return abs(a - b) <= rel * max(abs(b), 1.0)
