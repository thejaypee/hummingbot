#!/bin/bash
# Start all trading services: API server, bot, and dashboard

set -e

PYTHON="/home/sauly/miniconda3/envs/hummingbot/bin/python3.13"
PID_FILE="/tmp/hummingbot_services.pid"
LOG_DIR="/tmp/hummingbot_logs"

mkdir -p "$LOG_DIR"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      🚀 STARTING ALL TRADING SERVICES                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Kill any existing processes
if [ -f "$PID_FILE" ]; then
    echo "🧹 Cleaning up existing processes..."
    while read pid; do
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm "$PID_FILE"
fi

# Start Dashboard Server
echo "🌐 Starting Dashboard Server on :3000..."
nohup $PYTHON -m http.server 3000 > "$LOG_DIR/dashboard_server.log" 2>&1 &
DASH_PID=$!
echo "$DASH_PID" >> "$PID_FILE"
sleep 1
echo "✅ Dashboard Server started (PID: $DASH_PID)"
echo ""

# Start API Server
echo "📡 Starting API Server on :4000..."
nohup $PYTHON bot_api_server.py > "$LOG_DIR/api_server.log" 2>&1 &
API_PID=$!
echo "$API_PID" >> "$PID_FILE"
sleep 2
echo "✅ API Server started (PID: $API_PID)"
echo ""

# Start Trading Bot
echo "🤖 Starting Trading Bot (6-hour loop)..."
nohup $PYTHON -u uniswap_live_trader.py > "$LOG_DIR/trading_bot.log" 2>&1 &
BOT_PID=$!
echo "$BOT_PID" >> "$PID_FILE"
sleep 2
echo "✅ Trading Bot started (PID: $BOT_PID)"
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                   ✅ ALL SERVICES RUNNING                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Dashboard: http://localhost:3000/dashboard.html"
echo "📡 API Server: http://localhost:4000/api/dashboard"
echo ""
echo "📋 Logs:"
echo "   API Server: $LOG_DIR/api_server.log"
echo "   Trading Bot: $LOG_DIR/trading_bot.log"
echo ""
echo "🛑 To stop all services, run: ./stop_all_services.sh"
echo ""
