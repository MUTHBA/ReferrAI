@echo off
rem diagnose.bat - writes container status and recent logs to referrai-status.txt
cd /d "%~dp0"
(
  echo ==== docker compose ps
  docker compose ps -a
  echo.
  echo ==== frontend log
  docker compose logs --tail 80 frontend
  echo.
  echo ==== backend log
  docker compose logs --tail 60 backend
  echo.
  echo ==== nginx log
  docker compose logs --tail 20 nginx
) > referrai-status.txt 2>&1
echo Saved referrai-status.txt
