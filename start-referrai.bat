@echo off
rem ---------------------------------------------------------------------------
rem start-referrai.bat - double-click to start ReferrAI with Docker.
rem Needs Docker Desktop running. First start takes several minutes (images
rem build and the AI models train once). Loads demo data the first time.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
title ReferrAI

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker is not running. Start Docker Desktop, wait until it says "running", then run this again.
  pause
  exit /b 1
)

if exist cleanup-old-files.ps1 (
  echo Removing files the overhaul replaced...
  powershell -NoProfile -ExecutionPolicy Bypass -File cleanup-old-files.ps1
  del cleanup-old-files.ps1
)
if not exist .env copy .env.example .env >nul

echo.
echo Building and starting containers (first time: several minutes)...
docker compose up -d --build
rem nginx waits for a healthy backend; the first start can outlast that wait,
rem so keep checking and start anything that gave up.

echo.
echo Waiting for the backend (migrations + first-time model training)...
set /a tries=0
:wait
set /a tries+=1
curl -s http://localhost:8000/health | find "ok" >nul
if not errorlevel 1 goto up
if %tries% GEQ 90 (
  echo The backend did not start. Showing its log:
  docker compose logs --tail 60 backend
  pause
  exit /b 1
)
timeout /t 5 /nobreak >nul
goto wait

:up
docker compose up -d >nul 2>&1

echo.
echo Loading demo data (skipped if it is already there)...
docker compose exec -T backend python -m scripts.demo_history

echo.
echo ReferrAI is running at http://localhost
echo   Admin:   admin@referrai.io / Admin123!
echo   Partner: priya@demo.referrai.io / Partner123!
echo To stop it: docker compose down
start "" http://localhost
pause
