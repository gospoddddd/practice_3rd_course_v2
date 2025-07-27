#!/usr/bin/env python3
import argparse
from datetime import datetime, timedelta, date
import psycopg2

TABLE = '"mai"."table"'

def make_duplicates(conn_args, n_pairs=2):
    with psycopg2.connect(**conn_args) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT col1, col2, event_date FROM {TABLE} ORDER BY 1 LIMIT %s", (n_pairs,))
        base = cur.fetchall()
        for (c1, c2, d) in base:
            cur.execute(f"SELECT event_dttm, load_dttm FROM {TABLE} WHERE col1=%s AND col2=%s AND event_date=%s LIMIT 1",
                        (c1, c2, d))
            ev, ld = cur.fetchone()
            cur.execute(f'INSERT INTO {TABLE}(col1, col2, event_dttm, load_dttm, event_date) VALUES (%s,%s,%s,%s,%s)',
                        (c1, c2, ev, ld, d))
        conn.commit()
    print(f"Inserted {n_pairs} duplicate pairs (UNIQUE check should FAIL).")

def break_freshness(conn_args):
    with psycopg2.connect(**conn_args) as conn, conn.cursor() as cur:
        cur.execute(f"DELETE FROM {TABLE} WHERE load_dttm >= (NOW() - INTERVAL '3 days')")
        deleted = cur.rowcount
        conn.commit()
    print(f"Deleted {deleted} recent rows (Freshness by *dttm should FAIL).")

def insert_nulls(conn_args, n=3):
    with psycopg2.connect(**conn_args) as conn, conn.cursor() as cur:
        # Временно позволим NULL
        cur.execute('ALTER TABLE "mai"."table" ALTER COLUMN col2 DROP NOT NULL;')
        now = datetime.utcnow() - timedelta(days=5)
        for i in range(n):
            cur.execute(
                'INSERT INTO "mai"."table"(col1, col2, event_dttm, load_dttm, event_date) VALUES (%s,%s,%s,%s,%s)',
                (99999+i, None, now, now, date.today() - timedelta(days=40))
            )
        conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--action', required=True, choices=['make_duplicates','break_freshness','insert_nulls'])
    args = ap.parse_args()
    conn_args = dict(host=args.host, port=args.port, dbname=args.db, user=args.user, password=args.password)

    if args.action == 'make_duplicates':
        make_duplicates(conn_args)
    elif args.action == 'break_freshness':
        break_freshness(conn_args)
    elif args.action == 'insert_nulls':
        insert_nulls(conn_args)

if __name__ == "__main__":
    main()
