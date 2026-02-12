#!/bin/bash
# Check status of all trading services

echo "╔════════════════════════════════════════════════════════════╗"
echo "║           📊 TRADING SERVICES STATUS                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check API Server
if pgrep -f "bot_api_server.py" > /dev/null 2>&1; then
    API_PID=$(pgrep -f "bot_api_server.py" | head -1)
    echo "✅ API Server: RUNNING (PID: $API_PID)"
    API_UP=$(curl -s http://localhost:4000/health 2>/dev/null || echo "false")
    if [ "$API_UP" != "false" ]; then
        echo "   └─ Endpoint: http://localhost:4000/api/dashboard"
    fi
else
    echo "❌ API Server: STOPPED"
fi

echo ""

# Check Trading Bot
if pgrep -f "uniswap_live_trader.py" > /dev/null 2>&1; then
    BOT_PID=$(pgrep -f "uniswap_live_trader.py" | head -1)
    echo "✅ Trading Bot: RUNNING (PID: $BOT_PID)"
    echo "   └─ Location: /home/sauly/hummingbot/uniswap_live_trader.py"
else
    echo "❌ Trading Bot: STOPPED"
fi

echo ""
echo "📊 Dashboard: http://localhost:3000/dashboard.html"
echo "📡 API Endpoint: http://localhost:4000/api/dashboard"
echo ""
echo "🔧 Commands:"
echo "   ./start_all_services.sh  - Start all services"
echo "   ./stop_all_services.sh   - Stop all services"
echo "   ./status_services.sh     - Show this status"
echo ""
