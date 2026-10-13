"""Checks for 01-semantic-layer-and-metric-views."""

from helpers import ground_truth, semantic_model, utils

spark = utils.spark
MV = utils.METRIC_VIEW
ALL_TIME = 100_000  # days


def _summary():
    text = semantic_model.get_definition()
    assert text, (f"Metric view `{MV}` does not exist (or is not readable). Run Step 5 of the notebook, "
                  f"which creates it with CREATE VIEW ... WITH METRICS LANGUAGE YAML.")
    return semantic_model.summarize(semantic_model.parse_definition(text))


def _recon(question: str, approach: str):
    try:
        return utils.to_float(utils.query_scalar(
            f"SELECT value FROM {utils.fq('metric_reconciliation')} "
            f"WHERE question = '{question}' AND approach = '{approach}'"))
    except Exception:
        return None


def _measure(name: str, where: str = "") -> float:
    return utils.to_float(utils.query_scalar(f"SELECT MEASURE({name}) FROM {utils.fq(MV)} {where}"))


# ----------------------------------------------------------------- the build

def test_lab_views_exist(**kwargs):
    missing = [v for v in utils.LAB_VIEWS if not utils.table_exists(utils.fq(v))]
    assert not missing, f"Missing lab view(s): {missing}. Re-run 00-setup."


def test_refund_rollup_is_one_row_per_order(**kwargs):
    view = utils.fq(utils.REFUND_ROLLUP_VIEW)
    assert utils.table_exists(view), f"View `{utils.REFUND_ROLLUP_VIEW}` does not exist. Run Step 4."
    rows, orders = spark.sql(f"SELECT COUNT(*), COUNT(DISTINCT order_id) FROM {view}").collect()[0]
    assert rows == orders, (f"`{utils.REFUND_ROLLUP_VIEW}` has {rows} rows for {orders} orders. It must be "
                            f"one row per order, or every join to it duplicates order totals again.")
    rolled = utils.to_float(utils.query_scalar(f"SELECT SUM(refund_amount) FROM {view}"))
    raw = utils.to_float(utils.query_scalar(f"SELECT SUM(refund_amount) FROM {utils.fq('lab_refunds')}"))
    assert ground_truth.close(rolled, raw, 1e-9), f"The rollup lost refunds: {rolled:,.2f} vs {raw:,.2f} in lab_refunds."


def test_metric_view_has_join_measures_and_dimensions(**kwargs):
    s = _summary()
    assert len(s["joins"]) >= 1, "A metric view for this lab needs at least one join (customers, products, refunds)."
    assert len(s["measures"]) >= 3, f"Expected at least 3 measures, found {s['measures']}."
    assert len(s["dimensions"]) >= 2, f"Expected at least 2 dimensions (fields), found {s['dimensions']}."


def test_revenue_synonym_points_at_net_revenue(**kwargs):
    target = _summary()["synonyms"].get("revenue")
    assert target == "net_revenue", (
        f"The synonym 'revenue' points at {target!r}. When a business user says 'revenue' they mean the "
        f"company figure, net_revenue. Synonyms are how Genie and BI tools learn that.")


def test_metric_view_excludes_test_orders(**kwargs):
    assert _summary()["has_filter"], (
        "The metric view has no top-level `filter`. Test orders must be excluded from EVERY measure, which is "
        "exactly what a global filter is for (filter: NOT is_test_order).")


# ----------------------------------------------------------------- the reconciliation

def test_reconciliation_saved(**kwargs):
    assert utils.table_exists(utils.fq("metric_reconciliation")), (
        "Table `metric_reconciliation` does not exist. Run Step 7 (semantic_model.reconcile()).")


def test_raw_revenue_answers_really_disagree(**kwargs):
    a, b = _recon("revenue_90d", "raw_sales_ops"), _recon("revenue_90d", "raw_finance")
    assert a is not None and b is not None, "Re-run Step 7: the raw revenue rows are missing."
    assert ground_truth.close(a, ground_truth.raw_sales_ops_revenue(90)) and \
        ground_truth.close(b, ground_truth.raw_finance_fanout_revenue(90)), (
        "The saved raw answers no longer match the data. Re-run Step 7 (the window is relative to today).")
    assert not ground_truth.close(a, b, 0.001), "The two raw revenue answers should disagree; check the data setup."


def test_raw_active_customer_answers_really_disagree(**kwargs):
    m, c = _recon("active_customers", "raw_marketing_30d"), _recon("active_customers", "raw_cs_90d")
    assert m is not None and c is not None, "Re-run Step 7: the raw active-customer rows are missing."
    assert m != c, "Marketing (30d) and CS (90d) should disagree; check the data setup."


def test_metric_view_revenue_is_one_correct_number(**kwargs):
    total = _recon("revenue_90d", "metric_view_total")
    by_cat = _recon("revenue_90d", "metric_view_sum_of_categories")
    expected = ground_truth.net_revenue(90)
    assert total is not None and by_cat is not None, "Re-run Step 7: the metric view revenue rows are missing."
    assert ground_truth.close(total, by_cat, 1e-9), (
        f"Total ({total:,.2f}) and the sum of the category breakdown ({by_cat:,.2f}) differ. Through a "
        f"metric view, any breakdown must re-aggregate to the same total.")
    assert ground_truth.close(total, expected, 1e-6), (
        f"The metric view says {total:,.2f}; the governed definition gives {expected:,.2f}. Check the refund "
        f"join (must be the one-row-per-order rollup), the cancelled filter and the test-order filter.")


def test_metric_view_active_customers_is_one_correct_number(**kwargs):
    total = _recon("active_customers", "metric_view_total")
    by_region = _recon("active_customers", "metric_view_sum_of_regions")
    expected = ground_truth.active_customers(90)
    assert total is not None and by_region is not None, "Re-run Step 7: the active-customer rows are missing."
    assert int(total) == expected == int(by_region), (
        f"active_customers: total {total}, sum of regions {by_region}, governed definition {expected}.")


# ----------------------------------------------------------------- Challenge 1

def test_challenge_order_month_dimension(**kwargs):
    assert "order_month" in _summary()["dimensions"], (
        "Challenge 1: add a dimension named `order_month` (hint: DATE_TRUNC('MONTH', order_date)).")
    months, total = spark.sql(
        f"SELECT COUNT(*), SUM(r) FROM (SELECT order_month, MEASURE(net_revenue) AS r "
        f"FROM {utils.fq(MV)} GROUP BY order_month)").collect()[0]
    assert months == ground_truth.months_spanned(), (
        f"`order_month` produced {months} groups; the data spans {ground_truth.months_spanned()} calendar "
        f"months. It should truncate order_date to the month.")
    assert ground_truth.close(total, ground_truth.net_revenue(ALL_TIME), 1e-6), (
        "Net revenue summed over order_month should equal all-time net revenue.")


def test_challenge_refund_rate_measure(**kwargs):
    assert "refund_rate" in _summary()["measures"], "Challenge 1: add a measure named `refund_rate`."
    actual, expected = _measure("refund_rate"), ground_truth.refund_rate_all_time()
    hint = " It looks like a percentage; return a ratio between 0 and 1." if actual and actual > 1 else ""
    assert ground_truth.close(actual, expected, 1e-4), (
        f"refund_rate = {actual}; expected {expected:.6f}: refunds on completed orders divided by gross "
        f"bookings of completed orders (both excluding test orders, which the global filter does).{hint}")
