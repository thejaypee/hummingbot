#!/bin/bash
# ============================================
# AUTONOMOUS TRADER — Full Stack Launcher
# ============================================
# Starts: API Server, Autonomous Trader, Dashboard
# Logs:   /tmp/trader.log, /tmp/api_server.log
# Stop:   touch /tmp/trader_stop  (or use dashboard STOP button)
# ============================================

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Load env
if [ -f "$DIR/.env.local" ]; then
    set -a; source "$DIR/.env.local"; set +a
fi
if [ -f "$DIR/mcp/.env" ]; then
    set -a; source "$DIR/mcp/.env"; set +a
fi

# Clear any stale stop flags
rm -f /tmp/trader_stop /tmp/trader_sell_all

# Kill any existing instances
pkill -f "python3.*bot_api_server.py" 2>/dev/null || true
pkill -f "python3.*autonomous_trader.py" 2>/dev/null || true
sleep 1

echo "Starting API Server on port 4000..."
PYTHONUNBUFFERED=1 nohup python3 "$DIR/bot_api_server.py" > /tmp/api_server.log 2>&1 &
API_PID=$!
echo "  API PID: $API_PID"

# Wait for API to be ready
for i in $(seq 1 10); do
    if curl -s http://localhost:4000/health > /dev/null 2>&1; then
        echo "  API Server ready"
        break
    fi
    sleep 1
done

echo "Starting Dashboard Server on port 3000..."
PYTHONUNBUFFERED=1 nohup python3 "$DIR/dashboard_server.py" > /tmp/dashboard_server.log 2>&1 &
DASH_PID=$!
echo "  Dashboard PID: $DASH_PID"
sleep 1

echo "Starting Autonomous Trader..."
PYTHONUNBUFFERED=1 nohup python3 "$DIR/autonomous_trader.py" > /tmp/trader.log 2>&1 &
TRADER_PID=$!
echo "  Trader PID: $TRADER_PID"

# Open dashboard in browser
sleep 2
DASHBOARD="http://localhost:3000/dashboard.html"
if command -v wslview &> /dev/null; then
    wslview "$DASHBOARD"
elif command -v xdg-open &> /dev/null; then
    xdg-open "$DASHBOARD" 2>/dev/null
elif command -v sensible-browser &> /dev/null; then
    sensible-browser "$DASHBOARD" 2>/dev/null
elif [ -n "$BROWSER" ]; then
    "$BROWSER" "$DASHBOARD"
else
    # WSL fallback — open via Windows
    cmd.exe /c start "" "$(wslpath -w "$DIR/dashboard.html")" 2>/dev/null || true
fi

echo ""
echo "============================================"
echo "  TRADER RUNNING"
echo "============================================"
echo "  Dashboard : $DASHBOARD"
echo "  API       : http://localhost:4000"
echo "  Trader log: tail -f /tmp/trader.log"
echo "  API log   : tail -f /tmp/api_server.log"
echo "  Stop      : touch /tmp/trader_stop"
echo "============================================"
echo ""
echo "PIDs: API=$API_PID  Trader=$TRADER_PID"
