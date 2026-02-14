# Module Waitlist

Planned modules for the Autonomous Multi-Token Trader system.
Priority: HIGH / MEDIUM / LOW. Status: PLANNED / IN-PROGRESS / DONE.

---

## DONE

| Module | File | Description |
|--------|------|-------------|
| Token Registry | `token_registry.py` | SQLite-backed token/pool storage, chain-keyed |
| Liquidity Scout | `liquidity_scout.py` | GeckoTerminal + Gemini AI pool discovery |
| Token Monitor | `token_monitor.py` | Per-chain ERC20 balance scanner |
| Whitelist Manager | `whitelist.py` | Sender/token whitelist with audit log |
| Multichain Watcher | `multichain_watcher.py` | Transfer event detection across all chains |
| Trading Config | `config/trading_config.py` | Multi-chain V4 addresses + constants |
| Autonomous Trader | `autonomous_trader.py` | V4 swap execution, TP/SL, multichain pipeline |
| Bot API Server | `bot_api_server.py` | Flask REST API for dashboard |
| Dashboard | `dashboard.html` | Web UI for monitoring |
| Gemini Scout | `gemini_scout.py` | Gemini 2.5 Flash AI bridge for pool analysis |

---

## HIGH PRIORITY

| Module | File | Description | Notes |
|--------|------|-------------|-------|
| Multichain Gas Tank | `gas_tank.py` | Emergency gas refills across chains | Bridge ETH between chains when a chain drops below reserve. Auto-swap USDC→ETH on low-gas chains. |
| Run Loop Rewrite | `autonomous_trader.py` | Event-driven main loop consuming watcher queue | Replace single-chain block polling with multichain event queue |
| API Whitelist Endpoints | `bot_api_server.py` | CRUD for whitelist senders/tokens via REST | GET/POST /api/whitelist/senders, /api/whitelist/tokens |
| Dashboard Chain Column | `dashboard.html` | Chain as metadata column in all tables | Not a mode selector — chain is data |

---

## MEDIUM PRIORITY

| Module | File | Description | Notes |
|--------|------|-------------|-------|
| Position Sizing Engine | `position_sizer.py` | Dynamic position sizing based on liquidity depth | Scale position size to pool TVL, max slippage |
| Multi-hop Router | `multi_hop.py` | Route through intermediate tokens when no direct pool | Token→WETH→USDC, Token→DAI→USDC, etc. |
| Price Oracle Aggregator | `price_oracle.py` | Aggregate prices from multiple on-chain and off-chain sources | Chainlink, Uniswap TWAP, CoinGecko, redundant pricing |
| MEV Protection | `mev_shield.py` | Flashbots/private mempool submission | Prevent front-running on mainnet swaps |
| Telegram Notifier | `telegram_bot.py` | Real-time trade alerts via Telegram | Entry/exit notifications, daily PnL summary |

---

## LOW PRIORITY

| Module | File | Description | Notes |
|--------|------|-------------|-------|
| Backtester | `backtester.py` | Simulate strategies against historical data | Replay on-chain events, compute hypothetical PnL |
| Strategy Plugins | `strategies/` | Pluggable strategy modules (momentum, mean-reversion, etc.) | Hot-loadable, per-token strategy assignment |
| Portfolio Rebalancer | `rebalancer.py` | Auto-rebalance across chains by target weights | Cross-chain USDC allocation targets |
| Token Scoring Model | `token_scorer.py` | ML-based token quality scoring | Social signals, on-chain metrics, liquidity score |
| Audit Logger | `audit_log.py` | Immutable append-only trade + event log | JSON lines or SQLite WAL for compliance |
| Rate Limiter | `rate_limiter.py` | Per-chain RPC rate limiting with backoff | Prevent Alchemy/Infura throttling |

---

## Adding a Module

1. Create the file in the project root (or appropriate subdirectory)
2. Move the entry from PLANNED → IN-PROGRESS above
3. Wire it into `autonomous_trader.py` or `bot_api_server.py`
4. Add tests
5. Move to DONE when shipped
