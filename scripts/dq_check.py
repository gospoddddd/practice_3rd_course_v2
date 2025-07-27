#!/usr/bin/env python3
import argparse
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
import psycopg2
from psycopg2 import sql
import pandas as pd
import re

def get_columns(conn, schema, table):
    q = sql.SQL("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
        ORDER BY ordinal_position
    """)
    with conn.cursor() as cur:
        cur.execute(q, (schema, table))
        return cur.fetchall()

def rule_presence_dttm(cols):
    has = any(re.search(r'dttm', c[0], re.IGNORECASE) for c in cols)
    details = {'has_dttm': has, 'matched': [c[0] for c in cols if re.search(r'dttm', c[0], re.IGNORECASE)]}
    return has, details

def rule_notnull(conn, schema, table, columns):
    results = []
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}" ).format(sql.SQL(f'"{schema}"."{table}"')))
        total = cur.fetchone()[0]
        for col in columns:
            cur.execute(sql.SQL("SELECT COUNT(*) - COUNT({col}) FROM {tbl}")
                        .format(col=sql.Identifier(col),
                                tbl=sql.SQL(f'"{schema}"."{table}"')))
            nulls = cur.fetchone()[0]
            pct = (nulls/total) if total else 0.0
            results.append({'column': col, 'nulls': nulls, 'total': total, 'null_pct': pct})
    df = pd.DataFrame(results)
    pass_cond = (df['null_pct'] == 0).all()
    return pass_cond, df

def rule_unique(conn, schema, table, key_cols):
    if not key_cols:
        return True, pd.DataFrame(columns=['dup_count'] + key_cols)
    cols_ident = sql.SQL(", ").join(sql.Identifier(c) for c in key_cols)
    q = sql.SQL("""
        SELECT {cols_ident}, COUNT(*) AS dup_count
        FROM {tbl}
        GROUP BY {cols_ident}
        HAVING COUNT(*) > 1
        ORDER BY dup_count DESC
        LIMIT 100
    """).format(cols_ident=cols_ident, tbl=sql.SQL(f'"{schema}"."{table}"'))
    with conn.cursor() as cur:
        cur.execute(q)
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=key_cols + ['dup_count'])
    return df.empty, df

def rule_freshness_dttm(conn, schema, table, dttm_cols, days=2):
    if not dttm_cols:
        return False, {'reason': 'no_dttm_columns'}
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    max_ok = False
    max_values = {}
    with conn.cursor() as cur:
        for c in dttm_cols:
            cur.execute(sql.SQL("SELECT MAX({c}) FROM {t}").format(
                c=sql.Identifier(c), t=sql.SQL(f'"{schema}"."{table}"')))
            mx = cur.fetchone()[0]
            max_values[c] = mx
            if mx is not None and mx >= threshold:
                max_ok = True
    return max_ok, {'threshold_utc': threshold, 'max_values': max_values}

def rule_staleness_date(conn, schema, table, date_cols, days=2):
    if not date_cols:
        return True, {'reason': 'no_date_columns'}
    today = date.today()
    month_start = today.replace(day=1)
    threshold = today - timedelta(days=days)
    pass_any = False
    max_values = {}
    with conn.cursor() as cur:
        for c in date_cols:
            cur.execute(sql.SQL("SELECT MAX({c}) FROM {t}").format(
                c=sql.Identifier(c), t=sql.SQL(f'"{schema}"."{table}"')))
            mx = cur.fetchone()[0]
            max_values[c] = mx
            if mx is None:
                continue
            if mx >= threshold or (mx >= month_start and mx <= today):
                pass_any = True
    return pass_any, {'threshold_date': threshold, 'month_start': month_start, 'max_values': max_values}

def build_html(outdir, summaries):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    def badge(ok): return f"<span class='badge {'pass' if ok else 'fail'}'>{'PASS' if ok else 'FAIL'}</span>"
    html = ["""<!doctype html>
<html><head><meta charset="utf-8"><title>DQ Report (Extended)</title>
<style>
body { font-family: Arial, sans-serif; margin: 20px; }
h2 { margin-top: 28px; }
.badge { display:inline-block; padding:4px 8px; border-radius:6px; color:#fff; }
.badge.pass { background:#28a745; }
.badge.fail { background:#dc3545; }
table { border-collapse: collapse; width: 100%; max-width: 100%; }
th, td { border: 1px solid #ddd; padding: 6px; text-align:left; font-size: 13px; }
th { background:#f7f7f7; }
small { color:#666; }
.section { border:1px solid #eee; padding:12px; border-radius:8px; margin: 14px 0; }
pre { background:#fafafa; padding:8px; border:1px solid #eee; overflow-x:auto; }
</style></head><body>
<h1>Data Quality Report (расширенный)</h1>
"""]
    ok, info = summaries['presence_dttm']
    html.append(f"<div class='section'><h2>1) Наличие колонки *dttm {badge(ok)}</h2>")
    html.append(f"<p>Найдены *dttm столбцы: <b>{', '.join(info['matched']) if info['matched'] else 'нет'}</b></p></div>")
    ok, df = summaries['notnull']
    html.append(f"<div class='section'><h2>2) NOT NULL (кол-во и доля) {badge(ok)}</h2>")
    if df is not None and not df.empty:
        html.append(df.to_html(index=False))
    html.append("</div>")
    ok, dupdf = summaries['unique']
    html.append(f"<div class='section'><h2>3) UNIQUE (дубликаты по ключу) {badge(ok)}</h2>")
    html.append(f"<p>Ключ: {', '.join(summaries['meta']['unique_keys'])}</p>")
    if dupdf is not None and not dupdf.empty:
        html.append("<p><b>Обнаружены дубликаты:</b></p>")
        html.append(dupdf.to_html(index=False))
    else:
        html.append("<p>Дубликатов не обнаружено.</p>")
    html.append("</div>")
    ok, data = summaries['freshness_dttm']
    html.append(f"<div class='section'><h2>4) Свежесть по *dttm (последние 2 дня) {badge(ok)}</h2>")
    html.append(f"<p>Порог (UTC): {data.get('threshold_utc')}</p>")
    html.append("<table><tr><th>Колонка</th><th>MAX</th></tr>")
    for k,v in (data.get('max_values') or {}).items():
        html.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    html.append("</table></div>")
    ok, data = summaries['staleness_date']
    html.append(f"<div class='section'><h2>5) Устаревание по *date (≤2 дней или текущий месяц) {badge(ok)}</h2>")
    html.append(f"<p>Порог (date): {data.get('threshold_date')} | Начало месяца: {data.get('month_start')}</p>")
    html.append("<table><tr><th>Колонка</th><th>MAX</th></tr>")
    for k,v in (data.get('max_values') or {}).items():
        html.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    html.append("</table></div>")
    overall = all(summaries[k][0] for k in ['presence_dttm','notnull','unique','freshness_dttm','staleness_date'])
    html.append(f"<h2>Итоговый статус: {badge(overall)}</h2>")
    html.append("</body></html>")
    out = Path(summaries['meta']['outdir']); out.mkdir(parents=True, exist_ok=True)
    with open(out / 'report.html', 'w', encoding='utf-8') as f:
        f.write('\n'.join(html))
    if summaries['notnull'][1] is not None:
        summaries['notnull'][1].to_csv(out / 'notnull.csv', index=False)
    if summaries['unique'][1] is not None:
        summaries['unique'][1].to_csv(out / 'duplicates.csv', index=False)
    return overall

def main():
    ap = argparse.ArgumentParser(description='Extended DQ checks')
    ap.add_argument('--host', required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--schema', required=True)
    ap.add_argument('--table', required=True)
    ap.add_argument('--null-columns', nargs='*', default=['col1','col2','event_dttm','load_dttm','event_date'])
    ap.add_argument('--unique-keys', nargs='*', default=['col1','col2','event_date'])
    ap.add_argument('--outdir', default='artifacts')
    args = ap.parse_args()

    conn_args = dict(host=args.host, port=args.port, dbname=args.db, user=args.user, password=args.password)
    with psycopg2.connect(**conn_args) as conn:
        cols = get_columns(conn, args.schema, args.table)
        p_ok, p_info = rule_presence_dttm(cols)
        n_ok, n_df = rule_notnull(conn, args.schema, args.table, args.null_columns)
        u_ok, u_df = rule_unique(conn, args.schema, args.table, args.unique_keys)
        dttm_cols = [c for c,_ in cols if re.search(r'dttm', c, re.IGNORECASE)]
        f_ok, f_info = rule_freshness_dttm(conn, args.schema, args.table, dttm_cols, days=2)
        date_cols = [c for c,_ in cols if re.search(r'date', c, re.IGNORECASE)]
        s_ok, s_info = rule_staleness_date(conn, args.schema, args.table, date_cols, days=2)

    summaries = {
        'presence_dttm': (p_ok, p_info),
        'notnull': (n_ok, n_df),
        'unique': (u_ok, u_df),
        'freshness_dttm': (f_ok, f_info),
        'staleness_date': (s_ok, s_info),
        'meta': {
            'unique_keys': args.unique_keys,
            'outdir': args.outdir,
        }
    }
    overall = build_html(args.outdir, summaries)
    print('DQ OVERALL:', 'PASS' if overall else 'FAIL')
    if not overall:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
