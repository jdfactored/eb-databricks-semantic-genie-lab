"""
Curating Genie Ontology context (Exercise 4).

There is no "edit snippet" API: Genie Ontology infers snippets from your assets and ranks them by
authority. You curate it by changing the signals it reads, all of which are Unity Catalog objects:

  * certification   the `system.certification_status` governed tag (certified / deprecated).
                    Needs ASSIGN on that governed tag, granted by an admin.
  * descriptions    table, view, column and metric-view comments. Needs only ownership.
  * Pages (Beta)    governed business definitions inside a domain. UI only.

This module applies the first two and reads them back so the checks can verify them.
"""

import json
from typing import Dict, Optional

from helpers import lab_views, utils

spark = utils.spark
CERT_TAG = "system.certification_status"
GENIE_ONE_MARKER = "(added by Genie One)"
LEGACY_VIEW = "lab_daily_sales_summary"


def genie_one_url() -> str:
    try:
        return f"{utils.workspace_url()}/one?o={utils.workspace.get_workspace_id()}"
    except Exception:
        return f"{utils.workspace_url()}/one"


def certification(name: str) -> Optional[str]:
    """'certified', 'deprecated' or None, read from information_schema.table_tags."""
    try:
        return utils.query_scalar(f"""
            SELECT tag_value FROM `{utils.get_catalog()}`.information_schema.table_tags
            WHERE schema_name = '{utils.get_schema()}' AND table_name = '{name}' AND tag_name = '{CERT_TAG}'""")
    except Exception:
        return None


def set_certification(name: str, status: str) -> bool:
    """Try every SQL form that applies the tag to a view. Prints the admin ask on failure."""
    if status not in ("certified", "deprecated"):
        raise ValueError("status must be 'certified' or 'deprecated'")
    attempts = [
        f"SET TAG ON TABLE {utils.fq(name)} `{CERT_TAG}` = `{status}`",
        f"SET TAG ON VIEW {utils.fq(name)} `{CERT_TAG}` = `{status}`",
        f"ALTER VIEW {utils.fq(name)} SET TAGS ('{CERT_TAG}' = '{status}')",
    ]
    last_error = ""
    for sql in attempts:
        try:
            spark.sql(sql)
            print(f"Tagged {name}: {CERT_TAG} = {status}")
            return True
        except Exception as exc:
            last_error = str(exc).strip().splitlines()[0][:200]
    print(f"Could not tag {name} as {status}.\n  {last_error}\n\n"
          f"Applying `{CERT_TAG}` requires the ASSIGN permission on that governed tag. An account or\n"
          f"workspace admin grants it under Catalog > Governed tags > {CERT_TAG} > Permissions\n"
          f"(docs: https://docs.databricks.com/aws/en/data-governance/unity-catalog/certify-deprecate-data).\n"
          f"Carry on with the description-based curation in the next cell; it needs no extra grant.")
    return False


def deprecation_comment() -> str:
    return (f"DEPRECATED. Legacy gross bookings INCLUDING cancelled and test orders; the job stopped "
            f"refreshing. Do not use for revenue. Use the metric view "
            f"{utils.fq_plain(utils.METRIC_VIEW)} (measure net_revenue).")


def annotate_legacy_summary() -> None:
    """Rewrite the legacy view's description. Works with plain ownership, no governed-tag grant."""
    lab_views.bind_view(LEGACY_VIEW, comment=deprecation_comment())
    print(f"Updated the description of {LEGACY_VIEW}:\n  {deprecation_comment()}")


def comment_of(name: str) -> str:
    try:
        raw = spark.sql(f"DESCRIBE TABLE EXTENDED {utils.fq(name)} AS JSON").collect()[0][0]
        return json.loads(raw).get("comment") or ""
    except Exception:
        return utils.query_scalar(f"""
            SELECT comment FROM `{utils.get_catalog()}`.information_schema.tables
            WHERE table_schema = '{utils.get_schema()}' AND table_name = '{name}'""") or ""


def curation_status() -> Dict[str, bool]:
    legacy_comment = comment_of(LEGACY_VIEW)
    return {
        "metric_view_certified": certification(utils.METRIC_VIEW) == "certified",
        "legacy_view_deprecated_tag": certification(LEGACY_VIEW) == "deprecated",
        "legacy_view_deprecated_comment": legacy_comment.upper().startswith("DEPRECATED")
                                          and utils.METRIC_VIEW in legacy_comment,
    }


def genie_one_instruction(agent_title: str) -> str:
    return (f"Add this instruction to my Genie Agent \"{agent_title}\": Revenue always means net revenue: "
            f"completed orders minus refunds, excluding cancelled and test orders. {GENIE_ONE_MARKER}")
