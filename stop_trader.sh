#!/bin/bash
# Stop the autonomous trader gracefully
echo "Stopping Autonomous Trader..."
touch /tmp/trader_stop
sleep 2
pkill -f "python3.*autonomous_trader.py" 2>/dev/null || true
pkill -f "python3.*bot_api_server.py" 2>/dev/null || true
rm -f /tmp/trader_stop /tmp/trader_sell_all
echo "Stopped."
