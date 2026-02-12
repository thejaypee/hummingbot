#!/bin/bash
# Deploy Advanced ERC20 Trading Strategy - Balanced Settings
# This script prepares everything for MCP deployment

set -e

echo "🚀 ERC20 AUTOMATED TRADING BOT - BALANCED DEPLOYMENT"
echo "=================================================="
echo ""

# Step 1: Verify environment
echo "✓ Step 1: Checking environment..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi
echo "✓ Docker found"

# Step 2: Verify MCP is installed
echo ""
echo "✓ Step 2: Checking MCP Server..."
python -c "from hummingbot_mcp import main; print('✓ MCP Server ready')" 2>/dev/null || {
    echo "⚠ Installing MCP Server..."
    cd /home/sauly/hummingbot/mcp
    pip install -e . -q
    echo "✓ MCP Server installed"
}

# Step 3: Verify configuration file
echo ""
echo "✓ Step 3: Checking ERC20 configuration..."
CONFIG_FILE="/home/sauly/hummingbot/conf/controllers/advanced_erc20_tokens.yml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi
echo "✓ Configuration file found"

# Step 4: Display current configuration
echo ""
echo "📋 CURRENT CONFIGURATION:"
echo "========================"
grep -E "^(connector_name|trading_pair|id|position_size_quote|take_profit_pct|stop_loss_pct|max_concurrent_positions|daily_loss_limit)" "$CONFIG_FILE" | sed 's/^/  /'

# Step 5: Create deployment manifest
echo ""
echo "✓ Step 5: Creating deployment manifest..."
cat > /tmp/erc20_deployment.json << 'EOF'
{
  "strategy": "Advanced Trading Strategy",
  "asset_type": "ERC20 Tokens",
  "configuration_file": "/home/sauly/hummingbot/conf/controllers/advanced_erc20_tokens.yml",
  "settings": {
    "risk_level": "BALANCED",
    "position_size": "$500 per trade",
    "take_profit": "4%",
    "stop_loss": "2.5%",
    "max_positions": 5,
    "daily_loss_limit": "$1000"
  },
  "mcp_deployment": true,
  "status": "READY_TO_DEPLOY"
}
EOF
cat /tmp/erc20_deployment.json | python -m json.tool

# Step 6: Display MCP Server status
echo ""
echo "✓ Step 6: MCP Server Configuration"
echo "=================================="
echo ""
echo "The MCP server is configured in:"
echo "  Location: /home/sauly/hummingbot/mcp/"
echo "  Entry Point: main.py"
echo "  Credentials: ~/.hummingbot_mcp/"
echo ""

# Step 7: Next steps
echo ""
echo "✅ DEPLOYMENT READY!"
echo "=================="
echo ""
echo "🎯 NEXT STEPS:"
echo ""
echo "1. Add this to your Claude Code MCP config (~/.claude/mcp.json):"
cat << 'MCOCONFIG'

{
  "mcpServers": {
    "hummingbot-mcp": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--network",
        "host",
        "--env-file",
        "/home/sauly/hummingbot/mcp/.env",
        "-v",
        "$HOME/.hummingbot_mcp:/root/.hummingbot_mcp",
        "hummingbot/hummingbot-mcp:latest"
      ]
    }
  }
}

MCOCONFIG

echo ""
echo "2. Restart Claude Code"
echo ""
echo "3. In Claude Code, ask:"
echo '   "Deploy the ERC20 trading strategy from /home/sauly/hummingbot/conf/controllers/advanced_erc20_tokens.yml"'
echo ""
echo "4. Monitor with:"
echo '   "Show me current signals and positions"'
echo '   "What is my P&L?"'
echo '   "Display trading metrics dashboard"'
echo ""
echo "=================================================="
echo "📊 BALANCED SETTINGS SUMMARY"
echo "=================================================="
echo "Trading Pair: LINK-USDT (ERC20 Token on Binance)"
echo "Position Size: $500 per position"
echo "Max Positions: 5 concurrent"
echo "Take Profit: 4%"
echo "Stop Loss: 2.5%"
echo "Daily Loss Limit: $1000"
echo "Minimum Volume: 1.5x average"
echo ""
echo "Strategy will:"
echo "  ✓ Monitor volume, momentum (RSI/MACD), and price action"
echo "  ✓ Only trade when all signals align"
echo "  ✓ Automatically stop if $1000 daily loss reached"
echo "  ✓ Trade 24/7 with 3-5 min between positions"
echo ""
echo "=================================================="
