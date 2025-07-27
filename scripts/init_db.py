#!/usr/bin/env python3
import argparse
import time
from datetime import datetime, timedelta
import psycopg2

DDL_SCHEMA = 'CREATE SCHEMA IF NOT EXISTS "mai";'
DDL_TABLE = """
CREATE TABLE IF NOT EXISTS "mai"."table" (
    id SERIAL PRIMARY KEY,
    col1 INTEGER,
    col2 TEXT,
    col3 TIMESTAMPTZ
);
"""

def wait_for_db(conn_args, timeout=120):
    start = time.time()
    while True:
        try:
            with psycopg2.connect(**conn_args) as _:
                return
        except Exception:
            if time.time() - start > timeout:
                raise
            time.sleep(2)

def ensure_schema_table(conn_args):
    with psycopg2.connect(**conn_args) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(DDL_SCHEMA)
            cur.execute(DDL_TABLE)

def seed_data(conn_args, rows=100):
    with psycopg2.connect(**conn_args) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM "mai"."table";')
            count = cur.fetchone()[0]
            if count > 0:
                print(f"Table already has {count} rows; skipping seed.")
                return
            now = datetime.utcnow()
            for i in range(1, rows + 1):
                v1 = i if i not in {5, 15, 25, 35} else None
                v2 = f"text_{i}" if i not in {7, 17, 27} else None
                v3 = (now - timedelta(minutes=i)) if i not in {9, 19, 29} else None
                cur.execute(
                    'INSERT INTO "mai"."table"(col1, col2, col3) VALUES (%s, %s, %s)',
                    (v1, v2, v3),
                )
        conn.commit()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    args = ap.parse_args()
    conn_args = dict(host=args.host, port=args.port, dbname=args.db, user=args.user, password=args.password)
    print("Waiting for database to be ready...")
    wait_for_db(conn_args, timeout=120)
    print("Ensuring schema/table exist...")
    ensure_schema_table(conn_args)
    print("Seeding demo data if empty...")
    seed_data(conn_args)
    print("Database prepared.")

if __name__ == "__main__":
    main()
