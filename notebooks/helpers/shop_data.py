"""
Synthetic retail data for *Lumen Outfitters*, an outdoor-gear e-commerce company.

`generate_dataset()` is pure Python: no Spark, no SDK, so the whole dataset can be simulated
offline. `write_synthetic_tables()` is the only Spark-dependent function and imports Spark lazily.

Five tables, written to your schema and then bound to lab views by `lab_views.py`:

    synthetic_customers            one row per customer (incl. a handful of internal QA accounts)
    synthetic_products             one row per product
    synthetic_orders               one row per order, one product per order
    synthetic_refunds              one row per refund EVENT (an order can have several)
    synthetic_daily_sales_summary  a legacy pre-aggregated table with a column called `revenue`

Dates are relative to the day setup runs (the last day of data is yesterday). Volumes depend
only on the day INDEX, never on the calendar, so "the last 90 days" gives the same totals no
matter which day the lab runs. The checks still compute expected values from the data.

Ambiguities planted on purpose (repeated in INSTRUCTOR.md; keep them off the student branch if
you want discovery to be genuine):

  * Refunds are a separate table at refund-event grain. About 10% of completed orders are
    refunded and roughly 45% of those have 2-3 partial refunds, so a naive
    orders LEFT JOIN refunds duplicates order totals ("fan-out").
  * Internal QA accounts place test orders (`is_test_order = true`) that every KPI must exclude.
  * Roughly 4.5% of orders are cancelled.
  * ~30% of customers churn part-way through the window, so "active in 30 days" and
    "active in 90 days" are very different numbers.
  * `synthetic_daily_sales_summary.revenue` is gross INCLUDING cancelled and test orders, and the
    legacy job that fills it stopped 3 days before the end of the data. Its table comment just
    says "Daily revenue summary". It is the bait a Genie Agent over raw tables tends to take.
"""

import datetime as dt
import random
from typing import Dict, List, Optional

from helpers import reference_data as ref

DEFAULT_NUM_DAYS = 180
DEFAULT_SEED = 42
N_CUSTOMERS = 4200
N_INTERNAL_ACCOUNTS = 12
BASE_ORDERS_PER_DAY = 210
SUMMARY_LAG_DAYS = 3          # legacy summary job broke this many days before the end

CANCEL_RATE = 0.045
REFUND_RATE = 0.10
REFUND_EVENTS = ([1, 2, 3], [0.55, 0.33, 0.12])
FULL_REFUND_SHARE = 0.35
CHURN_SHARE = 0.30

ADJECTIVES = ["Summit", "Ridge", "Alpine", "Canyon", "Trail", "Glacier", "Cedar", "Basalt",
              "Aurora", "Granite", "Juniper", "Tundra"]
NOUNS = {
    "Footwear": ["Hiker", "Approach Shoe", "Trail Runner", "Mountaineering Boot"],
    "Outerwear": ["Shell Jacket", "Down Parka", "Fleece", "Rain Pant"],
    "Camping": ["Tent", "Sleeping Bag", "Stove", "Sleeping Pad", "Lantern"],
    "Climbing": ["Harness", "Rope", "Belay Device", "Chalk Bag"],
    "Accessories": ["Beanie", "Water Bottle", "Headlamp", "Trekking Socks"],
}
REFUND_REASONS = ["damaged", "wrong_size", "late_delivery", "changed_mind", "defective"]


def date_window(num_days: int, end_date: Optional[dt.date] = None):
    end_date = end_date or (dt.date.today() - dt.timedelta(days=1))
    return end_date - dt.timedelta(days=num_days - 1), end_date


def _pick(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _customers(rng: random.Random, num_days: int, start: dt.date) -> List[Dict]:
    rows = []
    for i in range(N_CUSTOMERS):
        new_in_window = rng.random() < 0.25
        first_idx = rng.randint(0, num_days - 20) if new_in_window else 0
        churns = rng.random() < CHURN_SHARE
        last_idx = rng.randint(first_idx + 10, num_days - 1) if churns else num_days - 1
        signup = (start + dt.timedelta(days=first_idx)) if new_in_window \
            else start - dt.timedelta(days=rng.randint(1, 720))
        rows.append(dict(
            customer_id=f"C{i + 1:05d}",
            region=_pick(rng, ref.REGIONS, ref.REGION_WEIGHTS),
            segment=_pick(rng, ref.SEGMENTS, ref.SEGMENT_WEIGHTS),
            signup_date=signup,
            acquisition_channel=_pick(rng, ["paid_search", "organic", "referral", "social"],
                                      [0.35, 0.35, 0.15, 0.15]),
            is_internal=False,
            _first=first_idx, _last=last_idx,
            _weight=rng.lognormvariate(0.0, 0.9),
        ))
    for j in range(N_INTERNAL_ACCOUNTS):
        rows.append(dict(
            customer_id=f"QA{j + 1:03d}", region=ref.REGIONS[j % len(ref.REGIONS)], segment="smb",
            signup_date=start - dt.timedelta(days=400), acquisition_channel="internal",
            is_internal=True, _first=0, _last=num_days - 1, _weight=1.0,
        ))
    return rows


def _products(rng: random.Random) -> List[Dict]:
    rows, n = [], 0
    for category, (count, lo, hi) in ref.CATEGORIES.items():
        for k in range(count):
            n += 1
            noun = NOUNS[category][k % len(NOUNS[category])]
            rows.append(dict(
                product_id=f"P{n:03d}",
                product_name=f"{ADJECTIVES[(n * 7) % len(ADJECTIVES)]} {noun}",
                category=category,
                list_price=round(rng.uniform(lo, hi), 2),
            ))
    return rows


def generate_dataset(num_days: int = DEFAULT_NUM_DAYS, seed: int = DEFAULT_SEED,
                     end_date: Optional[dt.date] = None) -> Dict[str, List[Dict]]:
    """Every row of every table as plain dicts. Deterministic for a given seed and num_days."""
    rng = random.Random(seed)
    start, end = date_window(num_days, end_date)
    customers = _customers(rng, num_days, start)
    products = _products(rng)
    external = [c for c in customers if not c["is_internal"]]
    internal = [c for c in customers if c["is_internal"]]
    cat_names = list(ref.CATEGORIES)
    cat_weights = [0.22, 0.20, 0.26, 0.10, 0.22]
    by_cat = {c: [p for p in products if p["category"] == c] for c in cat_names}

    raw_orders = []
    for idx in range(num_days):
        day = start + dt.timedelta(days=idx)
        eligible = [c for c in external if c["_first"] <= idx <= c["_last"]]
        weights = [c["_weight"] for c in eligible]
        volume = int(BASE_ORDERS_PER_DAY * (1 + 0.15 * idx / num_days) * rng.gauss(1.0, 0.08))
        for _ in range(max(volume, 0)):
            cust = rng.choices(eligible, weights=weights, k=1)[0]
            prod = rng.choice(by_cat[_pick(rng, cat_names, cat_weights)])
            qty = _pick(rng, [1, 2, 3], [0.78, 0.17, 0.05])
            disc = _pick(rng, [0.0, 0.10, 0.20], [0.75, 0.18, 0.07])
            raw_orders.append(dict(
                customer_id=cust["customer_id"], product_id=prod["product_id"],
                order_ts=dt.datetime.combine(day, dt.time(0)) + dt.timedelta(seconds=rng.randint(0, 86399)),
                quantity=qty, unit_price=prod["list_price"], discount_pct=disc,
                order_total=round(qty * prod["list_price"] * (1 - disc), 2),
                status="cancelled" if rng.random() < CANCEL_RATE else "completed",
                channel=_pick(rng, ref.CHANNELS, ref.CHANNEL_WEIGHTS),
                is_test_order=False,
            ))
        # QA load tests: a few large orders a day from internal accounts.
        for _ in range(_pick(rng, [0, 1, 2, 3, 4, 5], [0.25, 0.35, 0.22, 0.12, 0.04, 0.02])):
            prod = rng.choice(products)
            qty = rng.randint(3, 10)
            raw_orders.append(dict(
                customer_id=rng.choice(internal)["customer_id"], product_id=prod["product_id"],
                order_ts=dt.datetime.combine(day, dt.time(0)) + dt.timedelta(seconds=rng.randint(0, 86399)),
                quantity=qty, unit_price=prod["list_price"], discount_pct=0.0,
                order_total=round(qty * prod["list_price"], 2),
                status="completed", channel="web", is_test_order=True,
            ))

    raw_orders.sort(key=lambda o: o["order_ts"])
    for n, o in enumerate(raw_orders, start=1):
        o["order_id"] = f"O{n:07d}"
        o["order_date"] = o["order_ts"].date()

    refunds, r = [], 0
    for o in raw_orders:
        if o["status"] != "completed" or o["is_test_order"] or rng.random() >= REFUND_RATE:
            continue
        events = _pick(rng, *REFUND_EVENTS)
        share = 1.0 if rng.random() < FULL_REFUND_SHARE else rng.uniform(0.15, 0.70)
        total_cents = int(round(o["order_total"] * share * 100))
        cuts = sorted(rng.sample(range(1, total_cents), events - 1)) if total_cents > events else []
        parts = [b - a for a, b in zip([0] + cuts, cuts + [total_cents])] if cuts else [total_cents]
        when = o["order_date"]
        for cents in parts:
            when = when + dt.timedelta(days=rng.randint(1, 12))
            if when > end:          # refund not issued yet
                break
            r += 1
            refunds.append(dict(
                refund_id=f"R{r:06d}", order_id=o["order_id"],
                refund_date=when, refund_amount=round(cents / 100.0, 2),
                reason=rng.choice(REFUND_REASONS),
            ))

    summary = []
    last_refreshed = dt.datetime.combine(end - dt.timedelta(days=SUMMARY_LAG_DAYS), dt.time(4, 15))
    by_day: Dict[dt.date, List[Dict]] = {}
    for o in raw_orders:
        by_day.setdefault(o["order_date"], []).append(o)
    for idx in range(num_days - SUMMARY_LAG_DAYS):
        day = start + dt.timedelta(days=idx)
        todays = by_day.get(day, [])
        revenue = round(sum(o["order_total"] for o in todays), 2)
        summary.append(dict(
            sales_date=day, order_count=len(todays), revenue=revenue,
            avg_order_value=round(revenue / len(todays), 2) if todays else 0.0,
            last_refreshed_at=last_refreshed,
        ))

    return {
        "customers": [{k: v for k, v in c.items() if not k.startswith("_")} for c in customers],
        "products": products,
        "orders": raw_orders,
        "refunds": refunds,
        "daily_sales_summary": summary,
        "window": {"start": start, "end": end, "num_days": num_days, "seed": seed},
    }


# --------------------------------------------------------------------------- Spark side

TABLES = {
    "synthetic_customers": (
        "customers",
        "customer_id STRING, region STRING, segment STRING, signup_date DATE, "
        "acquisition_channel STRING, is_internal BOOLEAN",
        "Customer master. is_internal marks QA accounts.",
    ),
    "synthetic_products": (
        "products", "product_id STRING, product_name STRING, category STRING, list_price DOUBLE",
        "Product catalog.",
    ),
    "synthetic_orders": (
        "orders",
        "order_id STRING, customer_id STRING, product_id STRING, order_ts TIMESTAMP, order_date DATE, "
        "quantity INT, unit_price DOUBLE, discount_pct DOUBLE, order_total DOUBLE, status STRING, "
        "channel STRING, is_test_order BOOLEAN",
        "Orders. order_total is the amount charged at checkout.",
    ),
    "synthetic_refunds": (
        "refunds", "refund_id STRING, order_id STRING, refund_date DATE, refund_amount DOUBLE, reason STRING",
        "Refunds issued.",
    ),
    "synthetic_daily_sales_summary": (
        "daily_sales_summary",
        "sales_date DATE, order_count INT, revenue DOUBLE, avg_order_value DOUBLE, last_refreshed_at TIMESTAMP",
        "Daily revenue summary.",
    ),
}
MONEY_COLUMNS = {"unit_price", "order_total", "refund_amount", "revenue", "avg_order_value", "list_price"}


def write_synthetic_tables(num_days: Optional[int] = None, seed: Optional[int] = None) -> Dict:
    from pyspark.sql import functions as F
    from helpers import utils

    spark = utils.spark
    num_days = num_days or utils.get_history_days()
    seed = utils.get_seed() if seed is None else seed
    data = generate_dataset(num_days, seed)

    for table, (key, ddl, comment) in TABLES.items():
        cols = [c.strip().split(" ")[0] for c in ddl.split(",")]
        df = spark.createDataFrame([tuple(row[c] for c in cols) for row in data[key]], ddl)
        df = df.select(*[F.col(c).cast("decimal(12,2)").alias(c) if c in MONEY_COLUMNS else F.col(c)
                         for c in cols])
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(utils.fq(table))
        spark.sql(f"COMMENT ON TABLE {utils.fq(table)} IS '{comment}'")
        print(f"Created table: {table:32s} {len(data[key]):>7,} rows")

    w = data["window"]
    print(f"\nGenerated {len(data['orders']):,} orders and {len(data['refunds']):,} refund events "
          f"from {w['start']} to {w['end']} (seed {seed}).")
    return {"orders": len(data["orders"]), "refunds": len(data["refunds"]),
            "first_day": str(w["start"]), "last_day": str(w["end"])}
