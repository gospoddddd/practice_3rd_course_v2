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
      steps {
        withCredentials([usernamePassword(credentialsId: 'pg-user', usernameVariable: 'PGUSER', passwordVariable: 'PGPASSWORD')]) {
          sh '''
            . .venv/bin/activate
            python scripts/init_db.py \\
              --host "${PGHOST:-postgres}" --port "${PGPORT:-5432}" \\
              --db "${PGDATABASE:-appdb}" --user "$PGUSER" --password "$PGPASSWORD"
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
