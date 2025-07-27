// Telegram helper (works in both success/failure)
def notifyTelegram(String message) {
  withCredentials([string(credentialsId: 'telegram-bot-token', variable: 'TG_TOKEN'),
                   string(credentialsId: 'telegram-chat-id',   variable: 'TG_CHAT')]) {
    if ((env.TG_TOKEN ?: '').trim() && (env.TG_CHAT ?: '').trim()) {
      // двойные кавычки + экранированные $ для переменных shell
      sh(script: """#!/bin/bash -e
curl -s -X POST "https://api.telegram.org/bot\$TG_TOKEN/sendMessage" \
  -d chat_id="\$TG_CHAT" \
  --data-urlencode text="${message.replace('"','\\"')}" \
  -d parse_mode=Markdown || true
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
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
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
            python scripts/dq_check.py               --host "${PGHOST:-postgres}" --port "${PGPORT:-5432}"               --db "${PGDATABASE:-appdb}" --user "$PGUSER" --password "$PGPASSWORD"               --schema mai --table "table"               --null-columns col1 col2 event_dttm load_dttm event_date               --unique-keys col1 col2 event_date               --outdir artifacts
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
        notifyTelegram("✅ *DQ PASS* on ${env.JOB_NAME} #${env.BUILD_NUMBER}")
      }
    }
    failure {
      script {
        notifyTelegram("❌ *DQ FAIL* on ${env.JOB_NAME} #${env.BUILD_NUMBER}")
      }
    }
  }
}
parameters {
  booleanParam(name: 'TG_HEALTHCHECK', defaultValue: true, description: 'Проверять Telegram перед уведомлениями')
}

stage('Telegram Healthcheck') {
  when { expression { return params.TG_HEALTHCHECK } }
  steps {
    withCredentials([
      string(credentialsId: 'telegram-bot-token', variable: 'TELEGRAM_BOT_TOKEN'),
      string(credentialsId: 'telegram-chat-id',   variable: 'TELEGRAM_CHAT_ID')
    ]) {
      sh '''#!/bin/bash -e
set -o pipefail
mkdir -p artifacts

# 1) Тримминг значений (часто в секрете случайно попадает перевод строки)
TOKEN_TRIM=$(echo -n "$TELEGRAM_BOT_TOKEN" | tr -d '\\r\\n ')
CHAT_TRIM=$(echo -n "$TELEGRAM_CHAT_ID"  | tr -d '\\r\\n ')

echo "[getMe]"
R1=$(curl -sS "https://api.telegram.org/bot${TOKEN_TRIM}/getMe")
echo "$R1" | tee artifacts/tg_getMe.json >/dev/null
echo

echo "[getChat]"
R2=$(curl -sS -X POST "https://api.telegram.org/bot${TOKEN_TRIM}/getChat" \
  --data-urlencode "chat_id=${CHAT_TRIM}")
echo "$R2" | tee artifacts/tg_getChat.json >/dev/null
echo

echo "[sendMessage]"
MSG="TG healthcheck: ${JOB_NAME} #${BUILD_NUMBER} @ $(date -u +'%F %T UTC')"
R3=$(curl -sS -X POST "https://api.telegram.org/bot${TOKEN_TRIM}/sendMessage" \
  --data-urlencode "chat_id=${CHAT_TRIM}" \
  --data-urlencode "text=${MSG}")
echo "$R3" | tee artifacts/tg_sendMessage.json >/dev/null
echo

# 2) Простая проверка ok:true (без jq)
OK1=$(echo "$R1" | grep -c '"ok":true' || true)
OK2=$(echo "$R2" | grep -c '"ok":true' || true)
OK3=$(echo "$R3" | grep -c '"ok":true' || true)

echo "RESULTS: getMe=$OK1 getChat=$OK2 sendMessage=$OK3"
if [ "$OK1" -ne 1 ] || [ "$OK2" -ne 1 ] || [ "$OK3" -ne 1 ]; then
  echo "Telegram healthcheck failed (смотри artifacts/tg_*.json)" >&2
  exit 1
fi
'''
    }
  }
}
