#!/usr/bin/env python3
# Run: PYTHONPATH=. python3 app/db/migrations/001_change_tracking.py
import os, sqlite3

DB_PATH = os.getenv("DB_PATH", "dev.db")

def column_names(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}

def add_column_if_missing(cur, table, col_name, col_ddl):
    cols = column_names(cur, table)
    if col_name not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_ddl}")

def index_exists(cur, table, index_name):
    cur.execute(f"PRAGMA index_list({table})")
    return any(row[1] == index_name for row in cur.fetchall())

def create_index_if_possible(cur, table, index_name, cols):
    cols_set = column_names(cur, table)
    if all(c in cols_set for c in cols) and not index_exists(cur, table, index_name):
        cur.execute(f"CREATE INDEX {index_name} ON {table} ({', '.join(cols)})")

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 1) Versions table (idempotent)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS document_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        version_no INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        title TEXT,
        snapshot TEXT,             -- optional excerpt of extracted text
        change_type TEXT NOT NULL, -- ADDED | UPDATED | REMOVED
        fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(doc_id) REFERENCES documents(id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_doc_versions_doc_id_fetched ON document_versions (doc_id, fetched_at DESC);")

    # 2) Tracking fields on documents (add if missing)
    add_column_if_missing(cur, "documents", "current_hash",   "current_hash TEXT")
    add_column_if_missing(cur, "documents", "first_seen_at",  "first_seen_at TIMESTAMP")
    add_column_if_missing(cur, "documents", "last_seen_at",   "last_seen_at TIMESTAMP")
    add_column_if_missing(cur, "documents", "last_changed_at","last_changed_at TIMESTAMP")
    con.commit()

    # 3) Helpful index — prefer (jurisdiction, updated_at) if that column exists,
    #    otherwise use (jurisdiction, last_changed_at)
    cols = column_names(cur, "documents")
    if "updated_at" in cols:
        create_index_if_possible(cur, "documents", "ix_documents_jur_updated", ["jurisdiction", "updated_at"])
    elif "last_changed_at" in cols:
        create_index_if_possible(cur, "documents", "ix_documents_jur_last_changed", ["jurisdiction", "last_changed_at"])
    con.commit()

    cur.close(); con.close()
    print("migration ok")

if __name__ == "__main__":
    main()
