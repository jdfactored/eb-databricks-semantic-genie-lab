"""
Bind the lab views to the synthetic tables.

Every exercise, every metric view and every Genie Agent points at these views, never at the
synthetic tables directly. Re-pointing a view (for example at your company's real orders table)
changes the source for everything downstream without touching exercise code:

    lab_customers            synthetic_customers
    lab_products             synthetic_products
    lab_orders               synthetic_orders
    lab_refunds              synthetic_refunds              (one row per refund EVENT)
    lab_daily_sales_summary  synthetic_daily_sales_summary  (legacy; see INSTRUCTOR.md)
    lab_region_targets       region_targets                 (reference table)

The view comments are deliberately as thin as real-world ones usually are. Genie reads them.
"""

from typing import Optional

from helpers import utils

spark = utils.spark

VIEWS = {
    "lab_customers": ("synthetic_customers", "Customers."),
    "lab_products": ("synthetic_products", "Products."),
    "lab_orders": ("synthetic_orders", "Orders. order_total is the amount charged at checkout."),
    "lab_refunds": ("synthetic_refunds", "Refunds issued."),
    "lab_daily_sales_summary": ("synthetic_daily_sales_summary", "Daily revenue summary."),
    "lab_region_targets": ("region_targets", "90-day NET revenue target per region (USD)."),
}


def bind_view(view: str, comment: Optional[str] = None) -> None:
    source, default_comment = VIEWS[view]
    text = (comment or default_comment).replace("'", "\\'")
    spark.sql(f"CREATE OR REPLACE VIEW {utils.fq(view)} COMMENT '{text}' "
              f"AS SELECT * FROM {utils.fq(source)}")


def bind_views() -> None:
    for view in VIEWS:
        bind_view(view)
        print(f"Created view: {view}")
    print("\nLab views bound to the synthetic Lumen Outfitters data.")
