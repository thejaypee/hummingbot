@echo off
title Autonomous Trader
echo Starting Autonomous Trader...
wsl.exe -d Ubuntu -u sauly -- bash -ic "/home/sauly/hummingbot/start_trader.sh"
echo.
echo Press any key to view trader log...
pause >nul
wsl.exe -d Ubuntu -u sauly -- tail -f /tmp/trader.log
