#!/bin/bash
# Stop all trading services gracefully

PID_FILE="/tmp/hummingbot_services.pid"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      🛑 STOPPING ALL TRADING SERVICES                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No running services found (no PID file)"
    echo "Attempting to kill by process name..."
    pkill -f "bot_api_server.py" 2>/dev/null || true
    pkill -f "uniswap_live_trader.py" 2>/dev/null || true
    echo "✅ Done"
    exit 0
fi

# Kill each process gracefully
while read pid; do
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "🛑 Stopping service (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 1
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "⚠️  Process still running, force killing..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        echo "✅ Stopped"
    fi
done < "$PID_FILE"

rm "$PID_FILE"

# Verify all are stopped
echo ""
echo "📋 Verification:"
remaining=$(pgrep -f "bot_api_server.py\|uniswap_live_trader.py" | wc -l)
if [ "$remaining" -eq 0 ]; then
    echo "✅ All services stopped successfully"
else
    echo "⚠️  Warning: $remaining process(es) still running"
fi

echo ""
