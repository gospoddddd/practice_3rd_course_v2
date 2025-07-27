param(
  [switch]$Rebuild = $false
)

Write-Host "== DQ CI/CD quick start =="

if (-Not (Test-Path ".env")) {
  if (Test-Path ".env.example") {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Please edit REPO_URL and TELEGRAM_* if needed."
  } else {
    Write-Error "Missing .env.example"
    exit 1
  }
}

# Check docker compose
try {
  docker compose version | Out-Null
} catch {
  Write-Error "Docker Compose not found. Install Docker Desktop."
  exit 1
}

$composeArgs = "up -d"
if ($Rebuild) { $composeArgs = "up -d --build" }

Write-Host "Starting containers (docker compose $composeArgs)..."
docker compose up -d --build

Write-Host "`nOpen Jenkins at: http://localhost:8080"
Write-Host "Login: check .env (JENKINS_ADMIN_USER / JENKINS_ADMIN_PASSWORD)"
