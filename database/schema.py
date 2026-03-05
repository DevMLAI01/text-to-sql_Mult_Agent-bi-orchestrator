"""
Extracts the full DDL schema from the database via SQLAlchemy inspection.
Used by Node_1_Retriever to give the SQL Coder accurate table/column metadata.
"""

from sqlalchemy import inspect, Engine


def get_schema_ddl(engine: Engine) -> str:
    """
    Returns a human-readable DDL string for all tables in the database.
    Example output:
        TABLE: customers
          customer_id  TEXT  PK
          name         TEXT
          ...
    """
    inspector = inspect(engine)
    lines: list[str] = []

    for table_name in inspector.get_table_names():
        lines.append(f"TABLE: {table_name}")
        pk_cols = {col for col in inspector.get_pk_constraint(table_name).get("constrained_columns", [])}
        fk_map: dict[str, str] = {}
        for fk in inspector.get_foreign_keys(table_name):
            for col in fk["constrained_columns"]:
                ref = f"{fk['referred_table']}.{fk['referred_columns'][0]}"
                fk_map[col] = ref

        for col in inspector.get_columns(table_name):
            col_name = col["name"]
            col_type = str(col["type"])
            flags: list[str] = []
            if col_name in pk_cols:
                flags.append("PRIMARY KEY")
            if col_name in fk_map:
                flags.append(f"FK -> {fk_map[col_name]}")
            flag_str = "  " + ", ".join(flags) if flags else ""
            lines.append(f"  {col_name:<30} {col_type:<12}{flag_str}")

        lines.append("")  # blank line between tables

    return "\n".join(lines)
