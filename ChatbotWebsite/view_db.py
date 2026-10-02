import sqlite3
import os
import sys

# Default local database (Flask instance folder); pass another path as the first argument
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_ROOT, "instance", "lumora.db")

def print_table(cursor, table_name):
    print(f"\n--- {table_name.upper()} ---")
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [info[1] for info in cursor.fetchall()]
    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()
    if not rows:
        print("No entries found.")
        return
    # Print header
    print(" | ".join(columns))
    print("-" * 40)
    # Print rows
    for row in rows:
        print(" | ".join(str(cell) for cell in row))

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print("Tables in database:", tables)

    # Print each table
    for table in tables:
        print_table(cursor, table)

    conn.close()

if __name__ == "__main__":
    main()
