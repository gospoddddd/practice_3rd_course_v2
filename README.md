# DQ CI/CD (Jenkins + PostgreSQL, Windows-ready)

Автоматизированная проверка качества данных (количество/доля `NULL`) по колонкам `col1,col2,col3` в таблице `mai."table"`.  
Пайплайн разворачивается в Docker на Windows и поднимает Jenkins + Postgres. Jenkins создаёт job из этого репозитория и публикует HTML-отчёт.

## Что проверяем
- Подсчитываем `NULL` по каждой колонке (`col1`, `col2`, `col3`), а также долю `NULL`.
- Порог неуспеха: **5%** (`NULL% > 5%` → сборка падает).
- Отчёт: `artifacts/report.html` (+ CSV). Публикуется в Jenkins.

## Быстрый старт (Windows)
1. Установите **Docker Desktop** (Linux containers) и включите WSL2.
2. Склонируйте репозиторий, создайте `.env` из шаблона:
   ```powershell
   copy .env.example .env
   ```
3. Заполните в `.env`:
   - `REPO_URL` — URL этого репозитория на GitHub (публичный).
   - (опционально) `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` для уведомлений.
4. Запустите:
   ```powershell
   docker compose up -d --build
   ```
5. Откройте Jenkins: http://localhost:8080/ (логин/пароль из `.env`, по умолчанию `admin/admin`).  
   После старта JCasC создаст job **dq-pipeline**. Запустите сборку или настройте GitHub webhook для триггера по пушу.

## Детали реализации
- **БД**: PostgreSQL 16 (в контейнере). Схема `mai`, таблица `mai."table"` с колонками:
  - `col1 int`, `col2 text`, `col3 timestamptz`.
- **Демо-данные**: `scripts/init_db.py` создаёт схему/таблицу и заливает 100 строк с небольшой долей `NULL` (<5%), чтобы сборка проходила.
- **Проверка DQ**: `scripts/dq_check.py` соединяется с БД с использованием Jenkins Credentials (`pg-user`) и строит отчёт.
- **CI/CD**:
  - Jenkins в контейнере с предустановленными плагинами (Pipeline, Git, JCasC, Job DSL, HTML Publisher).
  - JCasC создаёт credentials (`pg-user`, `telegram-*`) и job **dq-pipeline** из `REPO_URL`.
  - Триггеры: poll SCM (каждые ~15 минут), nightly (~02:00), GitHub webhook (если настроен).
  - Артефакты: `artifacts/report.html` и `artifacts/dq_report.csv`.

## Переменные окружения (.env)
Смотрите `.env.example`. Ключевые:
- `POSTGRES_*` — доступы к БД внутри docker-compose.
- `PGHOST/PGPORT/PGDATABASE` — как Jenkins достучится до БД (по умолчанию `postgres:5432/appdb`).
- `REPO_URL` — URL GitHub-репозитория (обязателен для автосоздания job).
- `JENKINS_ADMIN_*` — учётка Jenkins.
- `TELEGRAM_*` — для уведомлений (опционально). Если пусто — уведомления пропускаются.

## Как это работает в сборке
1. **Setup venv**: ставим зависимости (`psycopg2-binary`, `pandas`).
2. **Init DB (demo)**: создаём `mai."table"` и записываем тестовые данные (если таблица пустая).
3. **Data Quality Check**: считаем `NULL` и долю по `col1/col2/col3`.
4. **Публикация**: архивируем артефакты + HTML Publisher.
5. **Уведомления**: при успехе/ошибке — Telegram (если заданы токен/чат).

## Локальные проверки
Можно запустить скрипты вне Jenkins (понадобится запущенный контейнер Postgres):
```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python scripts/init_db.py --host localhost --port 5432 --db appdb --user app --password app
python scripts/dq_check.py --host localhost --port 5432 --db appdb --user app --password app --schema mai --table "table" --columns col1 col2 col3 --threshold 0.05 --outdir artifacts
```

## Лицензия
MIT
