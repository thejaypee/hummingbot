# Automated Trading Strategies Setup Guide

This guide shows how to deploy and run 3 automated trading strategies using Hummingbot's Strategy v2 architecture.

## 📊 Available Strategies

### 1. **DCA Strategy** (Dollar Cost Averaging)
- **What it does**: Buys a fixed amount of an asset at regular intervals
- **Best for**: Long-term wealth building, reducing market timing risk
- **File**: `controllers/dca_strategy.py`
- **Config**: `conf/controllers/dca_btc_daily.yml`
- **Example**: Buy $100 of BTC every 24 hours

**Parameters**:
- `connector_name`: Exchange (binance, kucoin, coinbase, bybit, etc.)
- `trading_pair`: Asset (BTC-USDT, ETH-USDT, SOL-USDT, etc.)
- `order_amount_quote`: Amount per order ($100, $500, etc.)
- `order_interval_seconds`: Time between orders (3600=1hr, 86400=1day)

### 2. **Momentum Strategy**
- **What it does**: Trades based on moving average crossover signals
- **Best for**: Trending markets with clear directional bias
- **File**: `controllers/momentum_strategy.py`
- **Config**: `conf/controllers/momentum_eth.yml`
- **Example**: Buy when 5-period MA > 20-period MA, sell when reversed

**Parameters**:
- `short_window`: Short moving average period (5, 10, etc.)
- `long_window`: Long moving average period (20, 50, etc.)
- `candle_interval`: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
- `position_amount_quote`: Amount per position
- `take_profit_pct`: Exit profit percentage (2%, 3%, 5%, etc.)
- `stop_loss_pct`: Exit loss percentage (1%, 2%, etc.)
- `max_positions`: Max concurrent positions (1, 3, 5, etc.)

### 3. **Grid Trading Strategy**
- **What it does**: Places buy/sell orders at regular price intervals
- **Best for**: Ranging/sideways markets with high volatility
- **File**: `controllers/grid_trading_strategy.py`
- **Config**: `conf/controllers/grid_trading_btc.yml`
- **Example**: Buy every $1000 drop, sell every $1000 rise between $40k-$50k

**Parameters**:
- `lower_price`: Price floor for the grid
- `upper_price`: Price ceiling for the grid
- `grid_levels`: Number of buy/sell levels (10, 20, etc.)
- `grid_amount_quote`: Amount invested at each level

---

## 🚀 How to Deploy

### Option 1: Using the MCP Server (Recommended)
The MCP server can deploy strategies through Claude Code:

```python
# Through Claude:
"Deploy the DCA strategy from conf/controllers/dca_btc_daily.yml"
# Claude will:
# 1. Parse the configuration
# 2. Create the controller instance
# 3. Register executors
# 4. Start trading

"Show me my current positions and P&L"
# Claude will fetch portfolio data and performance metrics
```

### Option 2: Direct Python Deployment

```bash
# Activate environment
conda activate hummingbot

# Create and run a bot with the strategy
python << 'EOF'
from hummingbot.strategy_v2.controllers.run import StrategyRunner
from controllers.dca_strategy import DCAStrategyConfig, DCAStrategy

# Load config
config = DCAStrategyConfig(
    connector_name="binance",
    trading_pair="BTC-USDT",
    order_amount_quote=100,
    order_interval_seconds=86400
)

# Create and run strategy
runner = StrategyRunner([config], "DCA_Bot")
runner.start()
EOF
```

### Option 3: Using Configuration Files

```bash
# Deploy from YAML config
python -m hummingbot.strategy_v2.run_controller \
    --config-path conf/controllers/dca_btc_daily.yml \
    --connector-name binance \
    --trading-pair BTC-USDT
```

---

## 📝 Configuration Examples

### Example 1: Aggressive Bitcoin DCA
```yaml
# Buy Bitcoin every 4 hours with $50
connector_name: "binance"
trading_pair: "BTC-USDT"
order_amount_quote: 50
order_interval_seconds: 14400  # 4 hours
```

### Example 2: Conservative Ethereum Momentum
```yaml
# Long-term trend following with wide moving averages
connector_name: "binance"
trading_pair: "ETH-USDT"
short_window: 10
long_window: 50
candle_interval: "1h"
position_amount_quote: 1000
take_profit_pct: 5
stop_loss_pct: 2
max_positions: 2
```

### Example 3: Tight Grid for Range Trading
```yaml
# High frequency grid trading in tight range
lower_price: 42000
upper_price: 45000
grid_levels: 20  # More levels = smaller profits per trade
grid_amount_quote: 50  # Smaller amounts per level
```

---

## 🔧 Customization Guide

### Make DCA More Aggressive
- Increase `order_amount_quote` (e.g., $500 instead of $100)
- Decrease `order_interval_seconds` (e.g., 3600 for hourly buys)

### Make Momentum More Profitable
- Reduce `short_window` to 3-5 (faster signals, more trades)
- Reduce `stop_loss_pct` to 0.5-1% (tighter stops)
- Increase `take_profit_pct` to 5-10% (larger profits)

### Make Grid Trading Capture More
- Widen price range: `upper_price - lower_price`
- Increase `grid_levels` for more granular pricing
- Decrease `grid_amount_quote` to preserve capital across more levels

---

## 📊 Monitoring & Metrics

The strategies automatically track:

```python
{
    "total_volume": "...",        # Total traded amount
    "total_profit": "...",         # Realized P&L
    "win_rate": "...",            # % of profitable trades
    "active_positions": "...",     # Currently open positions
    "pending_orders": "...",       # Orders waiting to fill
    "average_entry_price": "...",  # Cost basis
    "unrealized_pnl": "..."        # Current position value
}
```

Check metrics through MCP:
```
"What's my current portfolio performance?"
"Show me all active positions"
"What's my profit on the DCA strategy?"
```

---

## ⚠️ Risk Management

### Before Going Live

1. **Test with Small Amounts**: Start with $50-100 positions
2. **Monitor First 24 Hours**: Watch the bot's behavior
3. **Set Max Positions**: Limit concurrent trades with `max_positions`
4. **Use Stop Loss**: Always set `stop_loss_pct` to protect capital
5. **Check API Keys**: Verify read/write permissions on exchange

### During Trading

1. **Daily Check-in**: Review positions and P&L
2. **Rebalance**: Adjust parameters if market changes
3. **Watch for Bugs**: Monitor logs for errors
4. **Adjust Stops**: Tighten stops in high volatility

### Emergency Controls

```
# Through MCP:
"Stop the DCA strategy"
"Cancel all pending orders"
"Close all positions"
"What orders are pending?"
```

---

## 🔄 Common Workflows

### Workflow 1: Start Simple DCA

1. Edit `conf/controllers/dca_btc_daily.yml`
2. Set: `connector_name`, `trading_pair`, `order_amount_quote`
3. Deploy through MCP: "Deploy DCA strategy"
4. Monitor: "Show my DCA positions"
5. Adjust if needed: Edit config and redeploy

### Workflow 2: Multi-Strategy Setup

```yaml
# Strategy 1: DCA for accumulation
- dca_btc_daily.yml (Buy $100 BTC daily)

# Strategy 2: Momentum for gains
- momentum_eth.yml (Trade ETH trends)

# Strategy 3: Grid for income
- grid_trading_btc.yml (Generate from price swings)
```

Deploy all three for diversified automated trading.

### Workflow 3: Backtest Before Live

```bash
# Test strategy on historical data
python -m hummingbot.strategy_v2.backtesting \
    --config conf/controllers/dca_btc_daily.yml \
    --start-date 2024-01-01 \
    --end-date 2024-02-10
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Strategy won't start | Check config YAML syntax, verify exchange API keys |
| Orders not filling | Check minimum order size on exchange, ensure sufficient balance |
| Price data missing | Verify internet connection, check exchange status |
| Positions not closing | Check stop loss/take profit prices, verify executor config |
| High slippage | Use limit orders instead, increase `take_profit_pct` |

---

## 📈 Strategy Selection Guide

| Market Condition | Best Strategy |
|---|---|
| **Sideways/Ranging** | Grid Trading |
| **Uptrend** | Momentum (+ DCA) |
| **Downtrend** | DCA (accumulate on dips) |
| **Volatile** | Grid Trading |
| **Low Volatility** | DCA (steady accumulation) |
| **Multi-Year Hold** | DCA (long-term dollar cost averaging) |

---

## 🎯 Next Steps

1. ✅ Edit a configuration file with your preferences
2. ✅ Deploy through MCP: "Deploy [strategy name]"
3. ✅ Monitor for 24 hours
4. ✅ Adjust parameters if needed
5. ✅ Add more strategies as you gain confidence

Start with **DCA** - it's the simplest and lowest risk!
