# Сценарии демонстрации PASS/FAIL — DQ CI/CD (Jenkins + PostgreSQL)

Этот файл описывает, как быстро показать **успешные** и **провальные** проверки качества данных (DQ) на таблице `mai."table"`
с правилами: наличие `*dttm`, `NOT NULL`, `UNIQUE`, свежесть по `*dttm` (≤2 дней), устаревание по `*date` (≤2 дней или текущий месяц).

> ⚙️ **Где запускать команды?** Есть два равнозначных варианта:
> - **Внутри контейнера Jenkins** — хост БД: `postgres` (имя Docker‑сервиса).
> - **С Windows‑хоста (PowerShell)** — хост БД: `localhost` (проброшенный порт 5432).

---

## 0) Предварительные условия

1. Контейнеры подняты:  
   ```powershell
   docker compose up -d
   docker compose ps
   ```
2. В репозитории применены правки **V2**: новая схема таблицы и расширенный `scripts/dq_check.py`.  
   В `Jenkinsfile` обновлён шаг DQ (см. `Jenkinsfile.patch.txt` в архиве V2).
3. В Jenkins есть job **`dq-pipeline`** с источником вашего репозитория.

---

## 1) Демонстрация **PASS** (чистые данные)

**Вариант A — внутри контейнера Jenkins (рекомендовано):**
```bash
docker exec -it dq_jenkins bash -lc "
  cd /var/jenkins_home/workspace/dq-pipeline || cd /workspace
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.txt
  python scripts/init_db.py \
    --host postgres --port 5432 \
    --db ${PGDATABASE:-appdb} --user ${PGUSER:-app} --password ${PGPASSWORD:-app}
"
# Затем запустить job dq-pipeline в Jenkins → все 5 правил должны быть PASS
```

**Вариант B — с Windows‑хоста (PowerShell):**
```powershell
# из корня репозитория (например, D:\Developing\MAI\dq-jenkins-postgres-win)
py -3 -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts\init_db.py --host localhost --port 5432 --db appdb --user app --password app
# Затем запусти job dq-pipeline в Jenkins → PASS
```

**Где смотреть отчёт?** В результате сборки в Jenkins открой **HTML Report**: `artifacts/report.html`.

---

## 2) Демонстрация **FAIL**

### 2.1. Дубликаты (UNIQUE FAIL)
Создадим точные дубликаты по ключу `col1,col2,event_date`.
- **Внутри Jenkins‑контейнера:**
  ```bash
  docker exec -it dq_jenkins bash -lc "
    cd /var/jenkins_home/workspace/dq-pipeline || cd /workspace
    . .venv/bin/activate
    python scripts/mutations.py --host postgres --port 5432 \
      --db ${PGDATABASE:-appdb} --user ${PGUSER:-app} --password ${PGPASSWORD:-app} \
      --action make_duplicates
  "
  ```
- **С Windows‑хоста (PowerShell):**
  ```powershell
  & .\.venv\Scripts\Activate.ps1
  python scripts\mutations.py --host localhost --port 5432 --db appdb --user app --password app --action make_duplicates
  ```

👉 Запусти job → в отчёте в секции **UNIQUE** появятся строки дублей, итоговый статус: **FAIL**.

---

### 2.2. Свежесть по `*dttm` (Freshness FAIL)
Удалим все записи за последние 3 дня по `load_dttm`.
- **Внутри Jenkins‑контейнера:**
  ```bash
  docker exec -it dq_jenkins bash -lc "
    cd /var/jenkins_home/workspace/dq-pipeline || cd /workspace
    . .venv/bin/activate
    python scripts/mutations.py --host postgres --port 5432 \
      --db ${PGDATABASE:-appdb} --user ${PGUSER:-app} --password ${PGPASSWORD:-app} \
      --action break_freshness
  "
  ```
- **С Windows‑хоста (PowerShell):**
  ```powershell
  & .\.venv\Scripts\Activate.ps1
  python scripts\mutations.py --host localhost --port 5432 --db appdb --user app --password app --action break_freshness
  ```

👉 Запусти job → в отчёте в секции **Свежесть по *dttm** максимальные значения будут старыми, итог: **FAIL**.

---

### 2.3. NOT NULL FAIL
Добавим строки с `NULL` в `col2`.
- **Внутри Jenkins‑контейнера:**
  ```bash
  docker exec -it dq_jenkins bash -lc "
    cd /var/jenkins_home/workspace/dq-pipeline || cd /workspace
    . .venv/bin/activate
    python scripts/mutations.py --host postgres --port 5432 \
      --db ${PGDATABASE:-appdb} --user ${PGUSER:-app} --password ${PGPASSWORD:-app} \
      --action insert_nulls
  "
  ```
- **С Windows‑хоста (PowerShell):**
  ```powershell
  & .\.venv\Scripts\Activate.ps1
  python scripts\mutations.py --host localhost --port 5432 --db appdb --user app --password app --action insert_nulls
  ```

👉 Запусти job → в секции **NOT NULL** появится ненулевая доля, итог: **FAIL**.

---

### 2.4. Устаревание по `*date` (Staleness FAIL)
Для демонстрации можно **насильно «устарить»** `event_date` (этого действия нет в `mutations.py`, поэтому используем SQL через `psql`).

- **Через контейнер PostgreSQL:**
  ```bash
  # изменит все даты на 90 дней назад
  docker exec -it dq_postgres psql -U app -d appdb -c \
    "UPDATE \"mai\".\"table\" SET event_date = CURRENT_DATE - INTERVAL '90 days';"
  ```
- **Либо внутри Jenkins‑контейнера через psql (если установлен), или малым Python‑скриптом:**
  ```bash
  docker exec -it dq_jenkins bash -lc "
    python - <<'PY'
import psycopg2
conn = psycopg2.connect(host='postgres', port=5432, dbname='appdb', user='app', password='app')
cur = conn.cursor()
cur.execute('UPDATE \"mai\".\"table\" SET event_date = CURRENT_DATE - INTERVAL ''90 days'';')
conn.commit()
print('event_date outdated')
PY
  "
  ```

👉 Запусти job → секция **Устаревание по *date** покажет старые даты (вне текущего месяца и старше 2 дней), итог: **FAIL**.

---

## 3) Возврат к **PASS**
В любой момент верни «чистое» состояние:
- **Jenkins‑контейнер:**
  ```bash
  docker exec -it dq_jenkins bash -lc "
    cd /var/jenkins_home/workspace/dq-pipeline || cd /workspace
    . .venv/bin/activate
    python scripts/init_db.py --host postgres --port 5432 \
      --db ${PGDATABASE:-appdb} --user ${PGUSER:-app} --password ${PGPASSWORD:-app}
  "
  ```
- **Windows (PowerShell):**
  ```powershell
  & .\.venv\Scripts\Activate.ps1
  python scripts\init_db.py --host localhost --port 5432 --db appdb --user app --password app
  ```
Затем запусти job → снова **PASS**.

---

## 4) Примечания и лайфхаки

- **Хост БД:** внутри Docker‑сети (в контейнерах) используем `postgres`; с хоста Windows — `localhost`.
- **Часовые пояса:** проверка свежести использует UTC‑порог — убедись, что время на хосте и в контейнерах корректное.
- **PowerShell venv:** активация `& .\.venv\Scripts\Activate.ps1` (а не `. .venv/bin/activate`, это Linux/WSL).
- **Отчёты:** HTML и CSV сохраняются в `artifacts/` и публикуются Jenkins HTML Publisher на каждой сборке.

Удачной демонстрации! 🚀
