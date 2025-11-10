#!/usr/bin/env python3
"""
Parse AWX Schema.sql file and generate CREATE TABLE DDL statements.

This script reads the Schema.sql file which contains INSERT statements into
information_schema.columns and converts them into proper CREATE TABLE DDL.
"""

import re
from collections import defaultdict
from pathlib import Path


class SchemaParser:
    """Parse AWX schema from information_schema.columns format."""

    TYPE_MAPPING = {
        "integer": "INTEGER",
        "bigint": "BIGINT",
        "character varying": "VARCHAR(255)",
        "text": "TEXT",
        "boolean": "BOOLEAN",
        "timestamp with time zone": "TIMESTAMPTZ",
        "jsonb": "JSONB",
        "uuid": "UUID",
        "double precision": "DOUBLE PRECISION",
        "smallint": "SMALLINT",
        "date": "DATE",
        "time without time zone": "TIME",
        "bytea": "BYTEA",
        "numeric": "NUMERIC",
    }

    # SQL reserved keywords that need to be quoted
    RESERVED_KEYWORDS = {
        "limit",
        "user",
        "order",
        "group",
        "table",
        "column",
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "grant",
        "revoke",
        "index",
        "view",
        "trigger",
        "check",
        "constraint",
        "foreign",
    }

    def __init__(self, schema_file: str):
        self.schema_file = Path(schema_file)
        self.tables: dict[str, list[tuple[str, str, str, int]]] = defaultdict(list)

    def parse(self) -> None:
        """Parse the schema file and extract table definitions."""
        with open(self.schema_file) as f:
            content = f.read()

        # Find all column definitions
        # Pattern: ('table_name','column_name',ordinal_position,'data_type','is_nullable')
        pattern = r"\('([^']+)','([^']+)',(\d+),'([^']+)','([^']+)'\)"
        matches = re.findall(pattern, content)

        for table_name, column_name, ordinal_pos, data_type, is_nullable in matches:
            self.tables[table_name].append((column_name, data_type, is_nullable, int(ordinal_pos)))

        # Sort columns by ordinal position for each table
        for table_name in self.tables:
            self.tables[table_name].sort(key=lambda x: x[3])

    def map_type(self, pg_type: str) -> str:
        """Map PostgreSQL type to DDL type."""
        return self.TYPE_MAPPING.get(pg_type, "TEXT")

    def quote_if_reserved(self, column_name: str) -> str:
        """Quote column name if it's a reserved keyword."""
        if column_name.lower() in self.RESERVED_KEYWORDS:
            return f'"{column_name}"'
        return column_name

    def generate_ddl(self, output_file: str) -> None:
        """Generate CREATE TABLE statements."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write("-- Generated AWX Schema DDL\n")
            f.write("-- Auto-generated from Schema.sql\n\n")
            f.write("SET CLIENT_ENCODING TO 'UTF8';\n")
            f.write("SET STANDARD_CONFORMING_STRINGS TO ON;\n\n")

            # Sort tables alphabetically for consistent output
            for table_name in sorted(self.tables.keys()):
                columns = self.tables[table_name]
                f.write(f"-- Table: {table_name}\n")
                f.write(f"CREATE TABLE IF NOT EXISTS {table_name} (\n")

                column_defs = []

                for column_name, data_type, is_nullable, _ in columns:
                    col_type = self.map_type(data_type)
                    nullable = "" if is_nullable == "YES" else " NOT NULL"
                    quoted_name = self.quote_if_reserved(column_name)

                    # Check if this is an ID column
                    if column_name == "id":
                        # ID columns should use SERIAL for auto-increment
                        if col_type in ("INTEGER", "BIGINT"):
                            serial_type = "SERIAL" if col_type == "INTEGER" else "BIGSERIAL"
                            column_defs.append(f"    {quoted_name} {serial_type} PRIMARY KEY")
                        else:
                            column_defs.append(f"    {quoted_name} {col_type} PRIMARY KEY{nullable}")
                    else:
                        column_defs.append(f"    {quoted_name} {col_type}{nullable}")

                f.write(",\n".join(column_defs))
                f.write("\n);\n\n")

            # Add indices for foreign key columns
            f.write("\n-- Indices for foreign key columns\n")
            for table_name in sorted(self.tables.keys()):
                columns = self.tables[table_name]
                for column_name, _, _, _ in columns:
                    # Create index for columns ending in _id (except 'id' itself)
                    if column_name.endswith("_id") and column_name != "id":
                        idx_name = f"idx_{table_name}_{column_name}"
                        f.write(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}({column_name});\n")


def main():
    """Main entry point."""
    import sys

    # Path to Schema.sql
    schema_path = Path(__file__).parent.parent.parent.parent / "Schema.sql"

    if not schema_path.exists():
        sys.exit(1)

    # Output path
    output_path = Path(__file__).parent.parent / "init" / "01-create-schema.sql"

    parser = SchemaParser(str(schema_path))
    parser.parse()
    parser.generate_ddl(str(output_path))


if __name__ == "__main__":
    main()
