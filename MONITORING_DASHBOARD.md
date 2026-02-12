# 📊 ERC20 Trading Bot - Monitoring Dashboard

## 🎯 Active Strategy

```
Strategy: Advanced Trading Strategy (Balanced)
Asset: ERC20 Tokens (LINK-USDT)
Status: 🟢 ACTIVE & RUNNING 24/7
Deployment: MCP Server (Hummingbot MCP)
```

---

## 📈 Real-Time Monitoring Commands

Use these commands in Claude Code to monitor your bot:

### **1. DAILY PERFORMANCE DASHBOARD**
```
"Show me today's trading performance dashboard with:
- Total trades executed
- Win rate percentage
- Profit/Loss summary
- Current open positions
- Performance vs daily loss limit"
```

**Expected Response:**
```
📊 TODAY'S PERFORMANCE (ERC20 Bot - Balanced)
================================================
Time Period: Feb 10, 2026 (00:00 - Current)

TRADES:
  Total Trades: 8
  Winning Trades: 5 (62.5% win rate ✓)
  Losing Trades: 3 (37.5%)

PROFITABILITY:
  Total Profit: +$187.50
  Total Loss: -$65.00
  Net P&L: +$122.50 ✓
  Daily Limit: -$1,000 (used 12.2%)

POSITIONS:
  Active Positions: 2/5
  Pending Orders: 1
  Next Position Entry: Ready

INDICATORS:
  Avg Win: +$37.50
  Avg Loss: -$21.67
  Profit Factor: 2.88x (excellent)
```

---

### **2. CURRENT SIGNALS & TECHNICAL ANALYSIS**
```
"Display the current market signals for LINK-USDT including:
- Current price and price change
- RSI value and interpretation
- MACD status
- Volume analysis
- Support and resistance levels
- Buy/Sell signal status"
```

**Expected Response:**
```
📡 CURRENT MARKET SIGNALS - LINK-USDT
================================================

PRICE ACTION:
  Current Price: $12.50
  24h Change: +2.1%
  5h Change: +1.2% ✓
  Volatility: MODERATE

TECHNICAL INDICATORS:
  RSI (14): 32 🟡 (Near oversold)
    → Interpretation: Weak selling, potential bounce

  MACD:
    MACD Line: +0.18
    Signal Line: +0.15
    Histogram: +0.03 (Bullish, weakening)
    Status: 🟢 BULLISH TURNING

  Bollinger Bands:
    Upper Band: $13.20
    Middle Band: $12.50
    Lower Band: $11.80
    Position: Mid-range (balanced)

VOLUME ANALYSIS:
  Current Volume: 5.2M LINK
  Average Volume (20d): 3.1M LINK
  Volume Ratio: 1.68x ✓ (Above 1.5x threshold)
  Status: 🟢 VOLUME CONFIRMED

PRICE LEVELS:
  Support: $12.00 (strong buying pressure)
  Resistance: $13.00 (selling pressure)

TRADING SIGNAL:
  Current Status: 🟡 NEUTRAL (waiting for stronger confirmation)
  Condition 1 (RSI < 30): ✗ (RSI = 32)
  Condition 2 (Volume Confirmed): ✓
  Condition 3 (MACD Turning): ✓
  Condition 4 (Price > Support): ✓

  → Waiting for: RSI to dip below 30 for strong BUY
```

---

### **3. ACTIVE POSITIONS & OPEN TRADES**
```
"Show me all my active positions with:
- Entry price and entry time
- Current unrealized P&L
- Distance to take profit
- Distance to stop loss
- Trade duration"
```

**Expected Response:**
```
📍 ACTIVE POSITIONS - LINK-USDT
================================================

POSITION #1:
  Entry Price: $12.30 (2 hours 15 min ago)
  Entry Time: 14:45 UTC
  Current Price: $12.50
  Quantity: 40.65 LINK

  Unrealized P&L: +$8.20 (+1.63%)
  Target (TP +4%): $12.79 → $10.29 to go
  Stop (SL -2.5%): $11.98 → $0.52 cushion ✓

  Status: 🟢 RUNNING WELL (closer to target)

POSITION #2:
  Entry Price: $12.00 (45 min ago)
  Entry Time: 16:45 UTC
  Current Price: $12.50
  Quantity: 41.67 LINK

  Unrealized P&L: +$20.83 (+3.47%)
  Target (TP +4%): $12.48 → Almost there!
  Stop (SL -2.5%): $11.70 → $0.80 cushion ✓

  Status: 🟢 ABOUT TO HIT TARGET

POSITION #3:
  Entry Price: $12.60 (30 min ago)
  Current Price: $12.50
  Quantity: 39.68 LINK

  Unrealized P&L: -$3.96 (-0.79%)
  Target (TP +4%): $13.10
  Stop (SL -2.5%): $12.29

  Status: 🟡 WAITING (patient position)

SUMMARY:
  Total Deployed Capital: $1,500 of $2,500 available
  Total Unrealized P&L: +$25.07
  Average Win Distance: 1.9% (halfway to target)
  Average Loss Distance: 0.79%
  Risk/Reward Ratio: 1:2.4 ✓ (favorable)
```

---

### **4. PENDING ORDERS**
```
"What orders are currently pending or about to execute?"
```

**Expected Response:**
```
⏳ PENDING ORDERS - LINK-USDT
================================================

PENDING ENTRY ORDERS:
  None currently pending

NEXT ENTRY CONDITION:
  Waiting for: RSI to reach 30 (currently 32)
  Estimated Time: 5-15 minutes at current price momentum
  Position Size: $500
  Projected Entry: $12.20-$12.40

TAKE PROFIT ORDERS:
  Position #2: Limit at $12.48 (active, very close)

STOP LOSS ORDERS:
  All 3 positions: Active with hardstops
```

---

### **5. WEEKLY PERFORMANCE TRENDS**
```
"Show me this week's trading performance with trends"
```

**Expected Response:**
```
📈 WEEKLY PERFORMANCE - LINK-USDT
================================================

DAILY BREAKDOWN:
  Mon (Feb 7): +$234.50 (12 trades, 67% win rate)
  Tue (Feb 8): +$145.80 (8 trades, 62% win rate)
  Wed (Feb 9): -$89.00 (6 trades, 33% win rate) ⚠️
  Thu (Feb 10): +$122.50 (8 trades, 62% win rate) ✓

WEEK SUMMARY:
  Total Trades: 34
  Total Profit: +$413.80
  Best Day: Monday (+$234.50)
  Worst Day: Wednesday (-$89.00)
  Win Rate: 59.7% (consistently above 50%)
  Profit Factor: 2.15x

TREND:
  📈 Recovering well after Wednesday dip
  🎯 On track for profitable week
  ✓ Balanced strategy performing as expected
```

---

### **6. RISK METRICS & SAFETY CHECK**
```
"Show me my risk metrics and safety status"
```

**Expected Response:**
```
⚠️ RISK METRICS & SAFETY STATUS
================================================

DAILY RISK MANAGEMENT:
  Daily Loss Limit: -$1,000
  Current Daily Loss: -$65.00
  Buffer Remaining: -$935.00 ✓
  Status: 🟢 SAFE (only 6.5% of limit used)

POSITION SIZING:
  Position Size: $500 each
  Max Positions: 5
  Active Positions: 3 (60% capacity)
  Available Capital: $2,500
  Deployed Capital: $1,500 (60%)

STOP LOSSES:
  All Positions: ✓ Active stops
  Average Stop Distance: 0.77%
  Worst Position: 0.52% to stop
  Status: 🟢 SAFE (all stops within tolerance)

VOLATILITY CHECK:
  LINK Volatility: 2.3% (normal for ERC20)
  Strategy Adapted: ✓ Yes (2.5% stops)
  Status: 🟢 BALANCED FOR CONDITIONS

DAILY LOSS CIRCUIT:
  Triggers at: -$1,000 daily loss
  Current: -$65 (6.5% triggered)
  Override Manual: Required if needed
  Status: 🟢 ACTIVE & MONITORING

OVERALL SAFETY: 🟢 ALL SYSTEMS GREEN
```

---

### **7. STRATEGY ADJUSTMENTS & OPTIMIZATION**
```
"Should I adjust any parameters? Show optimization recommendations"
```

**Expected Response:**
```
🔧 OPTIMIZATION RECOMMENDATIONS
================================================

CURRENT PERFORMANCE:
  Win Rate: 59.7% ✓ (above 50% target)
  Profit Factor: 2.15x ✓ (healthy)
  Max Drawdown: 2.1% ✓ (well within tolerance)

RECOMMENDATIONS:

1. ✓ NO CHANGES NEEDED (Keep current settings)
   - Strategy is performing well
   - Win rate above target
   - Risk/reward is favorable
   - Recommendation: LET IT RUN

2. OPTIONAL OPTIMIZATIONS (if you want to be more aggressive):
   - Increase position_size from $500 to $750
   - Increase max_positions from 5 to 7
   - Expected result: +30% more profit, +10% more risk

3. IF WIN RATE DROPS BELOW 45%:
   - Increase stop_loss from 2.5% to 3%
   - Increase daily_loss_limit from $1000 to $1500
   - Increase take_profit from 4% to 5%

NEXT ADJUSTMENT: Monitor for 1 week, then reassess
```

---

## 📱 Quick Commands Reference

### **ESSENTIAL (Use Daily)**
```
"Bot status check"
"Today's P&L"
"Active positions"
"Current signals"
```

### **RISK MANAGEMENT**
```
"Daily loss status"
"Risk metrics"
"Position exposure"
"Stop loss status"
```

### **OPTIMIZATION**
```
"Win rate analysis"
"Performance trends"
"Adjustment recommendations"
"Compare to previous week"
```

### **EMERGENCY**
```
"Stop all trading immediately"
"Close all positions now"
"What's my current exposure?"
"Cancel all pending orders"
```

---

## 🚨 Alert Thresholds

The strategy will automatically alert you if:

| Metric | Threshold | Action |
|--------|-----------|--------|
| Daily Loss | > $1,000 | ⛔ STOP trading |
| Position Count | = 5/5 | ⏸ Pause new entries |
| RSI Extreme | < 20 or > 80 | ⚠️ Caution signal |
| Volume Drop | < 1.0x average | ⏸ Hold for volume |
| Consecutive Losses | > 3 | ⚠️ Reassess |

---

## 📊 Dashboard View Template

Print this and update throughout the day:

```
╔════════════════════════════════════════════════════════════╗
║     ERC20 TRADING BOT - REAL-TIME DASHBOARD             ║
║     Strategy: Advanced (Balanced) | Asset: LINK-USDT      ║
╠════════════════════════════════════════════════════════════╣
║ TIME: [HH:MM]    PRICE: $[12.50]    CHANGE: [+1.2%]      ║
╠════════════════════════════════════════════════════════════╣
║ TODAY'S STATS:                                             ║
║  Trades: [8/10]  Win Rate: [62.5%]  P&L: [+$122.50]      ║
║  Active Positions: [3/5]  Daily Risk: [6.5% of $1000]    ║
╠════════════════════════════════════════════════════════════╣
║ SIGNAL: [NEUTRAL] RSI: [32] Volume: [1.68x] ✓             ║
║ Support: $12.00  |  Resistance: $13.00                    ║
╠════════════════════════════════════════════════════════════╣
║ NEXT ACTION: [Awaiting RSI < 30 for BUY - ~5-15 min]    ║
╚════════════════════════════════════════════════════════════╝
```

---

## 🎯 Daily Monitoring Routine

### **Morning Check (30 seconds)**
```
1. "What's my overnight P&L?"
2. "Any positions hit stop loss?"
3. "Anything I need to know?"
```

### **Mid-Day Check (1 minute)**
```
1. "Show active positions with unrealized P&L"
2. "What's the current signal?"
3. "Anything concerning?"
```

### **Evening Review (2 minutes)**
```
1. "Today's final performance"
2. "How close to daily loss limit?"
3. "Adjustment recommendations?"
```

### **Weekly Review (5 minutes)**
```
1. "Show weekly performance trends"
2. "Profit factor and win rate"
3. "Should I optimize any settings?"
```

---

## 💡 Pro Monitoring Tips

1. **Set Alerts**: Ask bot to notify you if daily loss reaches $800
2. **Track Patterns**: Note which times have best signals
3. **Log Winners**: Remember what led to winning trades
4. **Be Patient**: Let bot run, don't micromanage
5. **Weekly Assess**: Check once/week if adjustments needed

---

## ✅ Status: READY FOR LIVE TRADING

Your ERC20 Trading Bot is configured and ready to monitor!

**Next Step**: Deploy through Claude Code using the MCP configuration
