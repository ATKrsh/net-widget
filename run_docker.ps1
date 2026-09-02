# run_docker.ps1
# Helper script to run net-widget inside Docker on Windows using WSLg display forwarding.

# Check if docker is running
docker ps > $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running or docker command not found." -ForegroundColor Red
    Exit 1
}

# Run Docker Compose
Write-Host "Starting net-widget in Docker..." -ForegroundColor Cyan
docker compose up --build
