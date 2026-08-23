@echo off
setlocal
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
echo [SOOP Unified Core v2.5.0 Accuracy Ultimate] Starting...
docker compose up --build -d
if errorlevel 1 (
  echo Failed to start. Check Docker Desktop.
  exit /b 1
)
echo API: http://localhost:8080/v1/health
echo WS : ws://localhost:8080/v1/ws
endlocal
