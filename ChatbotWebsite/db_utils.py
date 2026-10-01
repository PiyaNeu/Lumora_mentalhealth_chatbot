"""Tiny SQLite schema helper.

The app has no migration tool, so when a model gains a column, an existing local
database would be missing it. This adds any missing columns in place (SQLite
supports ADD COLUMN). New tables are handled by db.create_all().
"""
from sqlalchemy import inspect, text


def add_missing_columns(db):
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
                if column.server_default is not None:
                    ddl += f" DEFAULT '{column.server_default.arg}'"
                conn.execute(text(ddl))
