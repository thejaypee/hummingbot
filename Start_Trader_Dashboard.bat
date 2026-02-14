@echo off
echo ==========================================
echo  Launching Hummingbot Trader Dashboard
echo ==========================================
echo.

:: Start the API server (port 4000) in WSL
echo Starting API server on port 4000...
wsl -d Ubuntu --cd /home/sauly/hummingbot -- python3 bot_api_server.py > /dev/null 2>&1 &

:: Start the dashboard server (port 3000) in WSL
echo Starting dashboard server on port 3000...
wsl -d Ubuntu --cd /home/sauly/hummingbot -- python3 dashboard_server.py > /dev/null 2>&1 &

:: Wait for servers to start
timeout /t 4 /nobreak > nul

:: Open browser
echo Opening dashboard in browser...
start http://localhost:3000/dashboard.html

echo.
echo ==========================================
echo  Dashboard: http://localhost:3000/dashboard.html
echo  API:       http://localhost:4000
echo ==========================================
echo.
echo Press any key to exit this window (servers keep running)...
pause > nul
