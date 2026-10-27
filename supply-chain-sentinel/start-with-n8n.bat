@echo off
REM Starts n8n + backend + dashboard, then opens the browser.
set PACE_SECONDS=2
start "Sentinel n8n" cmd /k "npx n8n"
start "Sentinel Backend" cmd /k "uvicorn backend.main:app --port 8000"
start "Sentinel Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 8 >nul
start http://localhost:5173
echo n8n editor: http://localhost:5678
