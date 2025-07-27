#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
import psycopg2
from psycopg2 import sql
import pandas as pd

def run_check(conn_args, schema, table, columns):
    with psycopg2.connect(**conn_args) as conn:
        with conn.cursor() as cur:
            ident_table = sql.Identifier(schema) + sql.SQL(".") + sql.Identifier(table)
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(ident_table))
            total = cur.fetchone()[0]

            results = []
            for col in columns:
                ident_col = sql.Identifier(col)
                query = sql.SQL("SELECT COUNT(*) - COUNT({}) FROM {}").format(ident_col, ident_table)
                cur.execute(query)
                nulls = cur.fetchone()[0]
                pct = (nulls / total) if total else 0.0
                results.append({"column": col, "null_count": nulls, "total": total, "null_pct": pct})
            return total, results

def write_reports(outdir, results, threshold):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    df['null_pct'] = df['null_pct'].round(6)
    df.to_csv(out / "dq_report.csv", index=False)

    status = "PASS" if (df['null_pct'] <= threshold).all() else "FAIL"
    rows = ""
    for _, r in df.iterrows():
        style = "" if r['null_pct'] <= threshold else " style='background:#ffdddd'"
        rows += f"<tr{style}><td>{r['column']}</td><td>{int(r['null_count'])}</td><td>{int(r['total'])}</td><td>{r['null_pct']:.4%}</td></tr>\n"

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DQ Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
h1 {{ margin: 0 0 10px 0; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:6px; color:#fff; }}
.badge.pass {{ background:#28a745; }}
.badge.fail {{ background:#dc3545; }}
table {{ border-collapse: collapse; width: 600px; max-width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align:left; }}
th {{ background:#f5f5f5; }}
small {{ color: #666; }}
</style>
</head>
<body>
  <h1>Data Quality: NULL counts</h1>
  <div>Status: <span class="badge {'pass' if status=='PASS' else 'fail'}">{status}</span></div>
  <small>Threshold: {threshold:.2%}</small>
  <table>
    <thead><tr><th>Column</th><th>NULL count</th><th>Total</th><th>NULL %</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>"""
    with open(out / "report.html", "w", encoding="utf-8") as f:
        f.write(html)
    return status

def main():
    ap = argparse.ArgumentParser(description="NULL checks per column")
    ap.add_argument('--host', required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--schema', required=True)
    ap.add_argument('--table', required=True)
    ap.add_argument('--columns', nargs='+', required=True)
    ap.add_argument('--threshold', type=float, default=0.05, help="Failure if NULL% > threshold (0..1)")
    ap.add_argument('--outdir', default='artifacts')
    args = ap.parse_args()

    conn_args = dict(host=args.host, port=args.port, dbname=args.db, user=args.user, password=args.password)

    total, results = run_check(conn_args, args.schema, args.table, args.columns)
    print(f"Total rows: {total}")
    for r in results:
        print(f"{r['column']}: nulls={r['null_count']} ({r['null_pct']:.2%})")

    status = write_reports(args.outdir, results, args.threshold)
    print(f"DQ STATUS: {status}")
    if status != "PASS":
        sys.exit(1)

if __name__ == "__main__":
    main()
