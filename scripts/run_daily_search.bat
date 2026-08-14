@echo off
REM Daily search + auto-email. Called by Windows Task Scheduler at 9:00 AM Eastern.
setlocal
cd /d "%~dp0.."

if not exist logs mkdir logs

where python >nul 2>&1
if errorlevel 1 (
  echo [%date% %time%] ERROR: python not found on PATH >> logs\daily_search.log
  exit /b 1
)

echo [%date% %time%] Starting daily-search with AUTO_SEND >> logs\daily_search.log
python -m prospect_pipeline daily-search >> logs\daily_search.log 2>&1
set EXITCODE=%ERRORLEVEL%
echo [%date% %time%] Finished with exit code %EXITCODE% >> logs\daily_search.log
exit /b %EXITCODE%
