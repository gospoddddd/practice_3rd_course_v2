# Сценарии для демонстрации FAIL

## 1) Дубликаты (UNIQUE FAIL)
```bash
. .venv/bin/activate
python scripts/mutations.py --host postgres --port 5432 --db appdb --user app --password app --action make_duplicates
```

## 2) Нет свежих данных (Freshness FAIL)
```bash
. .venv/bin/activate
python scripts/mutations.py --host postgres --port 5432 --db appdb --user app --password app --action break_freshness
```

## 3) NULL-ы (NOT NULL FAIL)
```bash
. .venv/bin/activate
python scripts/mutations.py --host postgres --port 5432 --db appdb --user app --password app --action insert_nulls
```
Затем запустите пайплайн Jenkins снова, чтобы увидеть FAIL в HTML-отчёте.
