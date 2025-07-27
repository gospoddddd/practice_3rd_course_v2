// Telegram helper (works in both success/failure) — с триммингом и безопасной отправкой
def notifyTelegram(String message) {
  withCredentials([string(credentialsId: 'telegram-bot-token', variable: 'TG_TOKEN'),
                   string(credentialsId: 'telegram-chat-id',   variable: 'TG_CHAT')]) {
    if ((env.TG_TOKEN ?: '').trim() && (env.TG_CHAT ?: '').trim()) {
      // двойные кавычки + тримминг на стороне shell
      sh(script: """#!/bin/bash -e
TOKEN_TRIM=\$(echo -n "\$TG_TOKEN" | tr -d '\\r\\n ')
CHAT_TRIM=\$(echo -n "\$TG_CHAT"  | tr -d '\\r\\n ')
curl -sS -X POST "https://api.telegram.org/bot\${TOKEN_TRIM}/sendMessage" \\
  --data-urlencode "chat_id=\${CHAT_TRIM}" \\
  --data-urlencode "text=${message.replace('"','\\\\"')}" || true
""")
    } else {
      echo "Telegram creds missing; skipping notification"
    }
  }
}

pipeline {
  agent any

  parameters {
    booleanParam(name: 'RESET_DB', defaultValue: false,
      description: 'Пересоздать демо-данные (init_db.py) перед проверкой')
    choice(name: 'MUTATION', choices: ['none','make_duplicates','break_freshness','insert_nulls'],
      description: 'Применить мутацию данных перед проверкой')

    // Новое: вкл/выкл подробную диагностику Telegram
    booleanParam(name: 'TG_DEBUG', defaultValue: true,
      description: 'Выполнить Telegram Debug (getMe/getChat/sendMessage) и сохранить ответы в артефакты')
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Setup Python venv') {
      steps {
        sh '''
          python3 -m venv .venv
          . .venv/bin/activate
          python -m pip install --upgrade pip
          pip install -r requirements.txt
        '''
      }
    }

    // Новое: диагностический прогон Telegram до основной логики
    stage('Telegram Debug') {
      when { expression { return params.TG_DEBUG } }
      steps {
        withCredentials([string(credentialsId: 'telegram-bot-token', variable: 'TG_TOKEN'),
                         string(credentialsId: 'telegram-chat-id',   variable: 'TG_CHAT')]) {
          sh '''#!/bin/bash -e
set -o pipefail
mkdir -p artifacts
TOKEN_TRIM=$(echo -n "$TG_TOKEN" | tr -d '\r\n ')
CHAT_TRIM=$(echo -n "$TG_CHAT"  | tr -d '\r\n ')

echo "LEN_TOKEN=$(printf %s "$TOKEN_TRIM" | wc -c)"
echo "LEN_CHAT=$(printf %s "$CHAT_TRIM" | wc -c)"
printf %s "$TOKEN_TRIM" | sha256sum | awk '{print "TOKEN_SHA256="$1}'
printf %s "$CHAT_TRIM"  | sha256sum | awk '{print "CHAT_SHA256="$1}'

echo "[getMe]"
R1=$(curl -sS "https://api.telegram.org/bot${TOKEN_TRIM}/getMe")
echo "$R1" | tee artifacts/tg_getMe.json >/dev/null
UNAME=$(echo "$R1" | sed -n 's/.*"username":"\\([^"]*\\)".*/\\1/p')
echo "getMe.username=${UNAME}"

echo "[getChat]"
R2=$(curl -sS -X POST "https://api.telegram.org/bot${TOKEN_TRIM}/getChat" \
  --data-urlencode "chat_id=${CHAT_TRIM}")
echo "$R2" | tee artifacts/tg_getChat.json >/dev/null

echo "[sendMessage]"
MSG="Healthcheck: ${JOB_NAME} #${BUILD_NUMBER} @ $(date -u +'%F %T UTC')"
R3=$(curl -sS -X POST "https://api.telegram.org/bot${TOKEN_TRIM}/sendMessage" \
  --data-urlencode "chat_id=${CHAT_TRIM}" \
  --data-urlencode "text=${MSG}")
echo "$R3" | tee artifacts/tg_sendMessage.json >/dev/null

OK1=$(echo "$R1" | grep -c '"ok":true' || true)
OK2=$(echo "$R2" | grep -c '"ok":true' || true)
OK3=$(echo "$R3" | grep -c '"ok":true' || true)
echo "OK: getMe=$OK1 getChat=$OK2 sendMessage=$OK3"
'''
        }
        archiveArtifacts artifacts: 'artifacts/tg_*.json', fingerprint: true, allowEmptyArchive: true
      }
    }

    stage('Init DB (demo)') {
      when { expression { params.RESET_DB } }   // <--- ВАЖНО
      steps {
        withCredentials([usernamePassword(credentialsId: 'pg-user', usernameVariable: 'PGUSER', passwordVariable: 'PGPASSWORD')]) {
          sh '''
            . .venv/bin/activate
            python scripts/init_db.py \
              --host "${PGHOST:-postgres}" --port "${PGPORT:-5432}" \
              --db "${PGDATABASE:-appdb}" --user "$PGUSER" --password "$PGPASSWORD"
          '''
        }
      }
    }

    stage('Apply Mutation (optional)') {
      when { expression { params.MUTATION != 'none' } }   // <--- ВАЖНО
      steps {
        withCredentials([usernamePassword(credentialsId: 'pg-user', usernameVariable: 'PGUSER', passwordVariable: 'PGPASSWORD')]) {
          sh '''
            . .venv/bin/activate
            python scripts/mutations.py \
              --host "${PGHOST:-postgres}" --port "${PGPORT:-5432}" \
              --db "${PGDATABASE:-appdb}" --user "$PGUSER" --password "$PGPASSWORD" \
              --action ${MUTATION}
          '''
        }
      }
    }

    stage('Data Quality Check') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'pg-user', usernameVariable: 'PGUSER', passwordVariable: 'PGPASSWORD')]) {
          sh '''
            . .venv/bin/activate
            python scripts/dq_check.py \
              --host "${PGHOST:-postgres}" --port "${PGPORT:-5432}" \
              --db "${PGDATABASE:-appdb}" --user "$PGUSER" --password "$PGPASSWORD" \
              --schema mai --table "table" \
              --null-columns col1 col2 event_dttm load_dttm event_date \
              --unique-keys col1 col2 event_date \
              --outdir artifacts
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'artifacts/*', fingerprint: true
      publishHTML (target: [
        reportName: 'DQ Report',
        reportDir: 'artifacts',
        reportFiles: 'report.html',
        keepAll: true,
        alwaysLinkToLastBuild: true,
        allowMissing: true
      ])
    }
    success {
      script {
        notifyTelegram("✅ DQ PASS — ${env.JOB_NAME} #${env.BUILD_NUMBER}")
      }
    }
    failure {
      script {
        notifyTelegram("❌ DQ FAIL — ${env.JOB_NAME} #${env.BUILD_NUMBER}")
      }
    }
  }
}
