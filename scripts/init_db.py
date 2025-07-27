#!/usr/bin/env python3
import argparse
import time
from datetime import datetime, timedelta, date
import psycopg2

DDL_DROP = 'DROP TABLE IF EXISTS "mai"."table";'
DDL_SCHEMA = 'CREATE SCHEMA IF NOT EXISTS "mai";'
DDL_TABLE = """
CREATE TABLE IF NOT EXISTS "mai"."table" (
    id SERIAL PRIMARY KEY,
    col1 INTEGER NOT NULL,
    col2 TEXT NOT NULL,
    event_dttm TIMESTAMPTZ NOT NULL,
    load_dttm TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_date DATE NOT NULL
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

def reset_and_seed(conn_args, rows=100):
    with psycopg2.connect(**conn_args) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(DDL_SCHEMA)
            cur.execute(DDL_DROP)
            cur.execute(DDL_TABLE)

        with conn.cursor() as cur:
            now = datetime.utcnow()
            for i in range(1, rows + 1):
                ev_dt = now - timedelta(hours=i)
                ld_dt = now - timedelta(hours=i % 36)
                ev_date = (date.today() - timedelta(days=i % 5))
                cur.execute(
                    'INSERT INTO "mai"."table"(col1, col2, event_dttm, load_dttm, event_date) VALUES (%s, %s, %s, %s, %s)',
                    (i, f"text_{i}", ev_dt, ld_dt, ev_date)
                )
    print("Table recreated and seeded with PASS data.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    args = ap.parse_args()

    conn_args = dict(host=args.host, port=args.port, dbname=args.db, user=args.user, password=args.password)
    print("Waiting for database...")
    wait_for_db(conn_args)
    reset_and_seed(conn_args, rows=120)

if __name__ == "__main__":
    main()
