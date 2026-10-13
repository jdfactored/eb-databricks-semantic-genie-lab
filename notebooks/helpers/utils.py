"""
Shared helpers for the Semantic Layer & Genie on Databricks lab.

Same pattern as the FinOps lab: one per-user schema namespaced by `current_user()`, and every
setting in one place, this file. DEFAULT_CATALOG below is the only place in the whole project
where the catalog name is written down.
"""

import re
from typing import Dict, List

from databricks.sdk import WorkspaceClient
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

_w = WorkspaceClient()
dbutils = _w.dbutils
workspace = _w  # exposed for helpers that call REST APIs (Genie Agents)

# Catalog where lab users have USE CATALOG + CREATE SCHEMA. Change it here only.
DEFAULT_CATALOG = "de_databricks_bp_wave_5"
SCHEMA_SUFFIX = "semantic"

DEFAULT_HISTORY_DAYS = 180
DEFAULT_SEED = 42

METRIC_VIEW = "sales_metrics"            # built in Exercise 1
REFUND_ROLLUP_VIEW = "order_refund_totals"  # built in Exercise 1

REFERENCE_TABLES = ("region_targets", "metric_glossary")
SYNTHETIC_TABLES = ("synthetic_customers", "synthetic_products", "synthetic_orders",
                    "synthetic_refunds", "synthetic_daily_sales_summary")
LAB_VIEWS = ("lab_customers", "lab_products", "lab_orders", "lab_refunds",
             "lab_daily_sales_summary", "lab_region_targets")


# --------------------------------------------------------------------------- parameters

def get_param(name: str, default: str) -> str:
    """A notebook widget wins if it exists; otherwise the default from this file."""
    try:
        value = dbutils.widgets.get(name)
        return value.strip() if value and value.strip() else default
    except Exception:
        return default


def get_catalog() -> str:
    return get_param("catalog", DEFAULT_CATALOG)


def get_history_days() -> int:
    return int(get_param("history_days", str(DEFAULT_HISTORY_DAYS)))


def get_seed() -> int:
    return int(get_param("seed", str(DEFAULT_SEED)))


# --------------------------------------------------------------------------- namespace

def get_current_user() -> str:
    return spark.sql("SELECT current_user()").collect()[0][0]


def get_base_user_schema() -> str:
    """jane.doe@factored.ai -> jane_doe"""
    base = get_current_user().split("@")[0].replace(".", "_").replace("-", "_").lower()
    return re.sub(r"[^a-z0-9_]", "_", base)


def get_schema() -> str:
    return f"{get_base_user_schema()}_{SCHEMA_SUFFIX}"


def fq(name: str) -> str:
    """Fully-qualified, quoted name of an object in the lab schema."""
    return f"`{get_catalog()}`.`{get_schema()}`.`{name}`"


def fq_plain(name: str) -> str:
    """Fully-qualified name without backticks: what you paste into the Genie Agent UI."""
    return f"{get_catalog()}.{get_schema()}.{name}"


def get_configs() -> Dict[str, str]:
    catalog, schema = get_catalog(), get_schema()
    configs = {
        "catalog": catalog,
        "base_user": get_base_user_schema(),
        "schema": schema,
        "metric_view": f"{catalog}.{schema}.{METRIC_VIEW}",
    }
    for name in LAB_VIEWS + REFERENCE_TABLES:
        configs[name] = f"{catalog}.{schema}.{name}"
    return configs


def use_lab_schema() -> Dict[str, str]:
    """
    Point the session at the lab schema so `%sql` cells can use unqualified names
    such as `lab_orders`. Every exercise notebook calls this in its first cell.
    """
    cfg = get_configs()
    spark.sql(f"USE CATALOG `{cfg['catalog']}`")
    spark.sql(f"USE SCHEMA `{cfg['schema']}`")
    return cfg


def workspace_url() -> str:
    return workspace.config.host.rstrip("/")


# --------------------------------------------------------------------------- tables

def table_exists(full_table_name: str) -> bool:
    try:
        spark.sql(f"DESCRIBE TABLE {full_table_name}")
        return True
    except Exception:
        return False


def get_column_names(full_table_name: str) -> List[str]:
    return [f.name for f in spark.table(full_table_name).schema.fields]


def get_table_row_count(full_table_name: str) -> int:
    return spark.table(full_table_name).count()


def query_scalar(sql: str):
    rows = spark.sql(sql).collect()
    return rows[0][0] if rows else None


def to_float(value) -> float:
    """Decimal / int / str -> float, None stays None."""
    return None if value is None else float(value)
