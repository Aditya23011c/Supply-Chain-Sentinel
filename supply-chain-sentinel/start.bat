@echo off
REM Starts the Sentinel backend + dashboard and opens the browser.
set PACE_SECONDS=2
start "Sentinel Backend" cmd /k "uvicorn backend.main:app --port 8000"
start "Sentinel Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 5 >nul
start http://localhost:5173
