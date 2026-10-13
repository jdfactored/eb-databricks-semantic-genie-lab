"""
Business reference data for the fictional retailer *Lumen Outfitters*.

Pure Python at import time (no Spark, no SDK), so the data generator can be simulated offline.
Spark is imported lazily inside `create_reference_tables()`.

    region_targets   one row per region: the 90-day NET revenue target finance signed off on.
                     Small, region-grain lookup. Exercise 2 adds it to a Genie Agent next to the
                     metric view, because a lookup at a metric-view dimension's grain is safe.
    metric_glossary  the company's written definitions. This is the "policy" the metric view
                     implements. Two analysts who never read it produce two different numbers.
"""

REGIONS = ["NA", "EMEA", "APAC", "LATAM"]
REGION_WEIGHTS = [0.42, 0.30, 0.18, 0.10]
SEGMENTS = ["consumer", "smb"]
SEGMENT_WEIGHTS = [0.78, 0.22]
CHANNELS = ["web", "app", "marketplace"]
CHANNEL_WEIGHTS = [0.55, 0.30, 0.15]

# category: (number of products, min list price, max list price)
CATEGORIES = {
    "Footwear":    (8, 60.0, 220.0),
    "Outerwear":   (8, 80.0, 420.0),
    "Camping":     (10, 25.0, 380.0),
    "Climbing":    (6, 15.0, 260.0),
    "Accessories": (8, 9.0, 70.0),
}

# 90-day NET revenue targets per region (USD). Set so that exactly one region is clearly the
# furthest below target, both in absolute dollars and as a percentage (Exercise 2 Challenge).
# Calibrated against the seeded generator (seed 42); see INSTRUCTOR.md.
REGION_TARGETS = [
    ("NA",    1_690_000.0),
    ("EMEA",  1_050_000.0),
    ("APAC",    810_000.0),
    ("LATAM",   360_000.0),
]

METRIC_GLOSSARY = [
    ("net_revenue",
     "Revenue. The company revenue figure. Order totals of completed orders minus every refund "
     "issued against those orders, attributed to the ORDER date. Excludes cancelled orders and "
     "internal test orders.",
     "Finance (CFO office)"),
    ("gross_revenue",
     "Gross bookings / GMV. Order totals of completed orders before refunds. Excludes cancelled "
     "and test orders. Never report this as 'revenue'.",
     "Finance (CFO office)"),
    ("active_customers",
     "A customer with at least one completed, non-test order in the trailing 90 days ending "
     "yesterday. Marketing's 30-day 'recently active' count is a campaign metric, not this KPI.",
     "RevOps"),
    ("test_orders",
     "Orders placed by internal QA accounts (is_test_order = true). Excluded from every KPI.",
     "Data Engineering"),
]


def create_reference_tables() -> None:
    from helpers import utils

    spark = utils.spark

    def _save(df, name: str) -> None:
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(utils.fq(name))
        print(f"Created table: {name}")

    _save(spark.createDataFrame(REGION_TARGETS, "region STRING, net_revenue_target_90d DOUBLE"),
          "region_targets")
    spark.sql(f"COMMENT ON TABLE {utils.fq('region_targets')} IS "
              f"'90-day NET revenue target per region (USD). One row per region.'")
    _save(spark.createDataFrame(METRIC_GLOSSARY, "metric STRING, definition STRING, owner STRING"),
          "metric_glossary")
