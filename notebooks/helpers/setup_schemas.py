"""Create / drop the per-student `<you>_semantic` schema."""

from helpers import utils

spark = utils.spark


def schema_exists(catalog: str, schema: str) -> bool:
    try:
        spark.sql(f"DESCRIBE SCHEMA `{catalog}`.`{schema}`")
        return True
    except Exception:
        return False


def _grant_options(catalog: str, schema: str, user: str) -> str:
    return (
        f"  -- Option A: let lab users create their own schemas\n"
        f"  GRANT USE CATALOG, CREATE SCHEMA ON CATALOG {catalog} TO `account users`;\n\n"
        f"  -- Option B: pre-create your schema and hand it over\n"
        f"  CREATE SCHEMA IF NOT EXISTS {catalog}.{schema};\n"
        f"  GRANT USE CATALOG ON CATALOG {catalog} TO `{user}`;\n"
        f"  GRANT ALL PRIVILEGES ON SCHEMA {catalog}.{schema} TO `{user}`;\n"
    )


def create_user_schema() -> None:
    """
    Create the lab schema, or reuse it if an instructor pre-created it.
    Reusing means a student does not need CREATE SCHEMA, only privileges on their schema.
    """
    catalog, schema = utils.get_catalog(), utils.get_schema()

    if schema_exists(catalog, schema):
        print(f"Reusing existing schema: {catalog}.{schema}")
    else:
        try:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}` "
                      f"COMMENT 'Semantic layer & Genie lab schema - safe to drop with 99-cleanup'")
            print(f"Created schema: {catalog}.{schema}")
        except Exception as exc:
            user = utils.get_current_user()
            first_line = str(exc).strip().splitlines()[0][:200]
            raise PermissionError(
                f"Could not create {catalog}.{schema}.\n  {first_line}\n\n"
                f"Ask your instructor to run ONE of these:\n\n"
                f"{_grant_options(catalog, schema, user)}\n"
                f"If your cohort uses a different catalog, change DEFAULT_CATALOG in helpers/utils.py."
            ) from None

    utils.use_lab_schema()


def print_instructor_grants(student_email: str = "student@example.com") -> None:
    """Print the exact GRANT statements for this cohort's catalog (used by INSTRUCTOR.md)."""
    catalog = utils.get_catalog()
    base = student_email.split("@")[0].replace(".", "_").replace("-", "_").lower()
    print(_grant_options(catalog, f"{base}_{utils.SCHEMA_SUFFIX}", student_email))


def clean_up_schema() -> None:
    catalog, schema = utils.get_catalog(), utils.get_schema()
    spark.sql(f"DROP SCHEMA IF EXISTS `{catalog}`.`{schema}` CASCADE")
    print(f"Dropped schema: {catalog}.{schema}")
