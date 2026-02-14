#!/usr/bin/env python3
"""
BOT API SERVER — Multi-token dashboard + emergency controls.
Serves real bot data to the dashboard, supports STOP and SELL ALL commands.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from config.trading_config import CHAINS, SELL_ALL_FLAG, STATE_FILE, STOP_FLAG, TRADES_FILE, WALLET_FILE
from token_registry import TokenRegistry
from whitelist import WhitelistManager

load_dotenv(Path("/home/sauly/hummingbot/.env.local"))

app = Flask(__name__)
CORS(app)

registry = TokenRegistry()
whitelist = WhitelistManager()

# Initialize data files
for fpath, default in [
    (TRADES_FILE, []),
    (WALLET_FILE, {
        "eth": 0, "usdc": 0, "weth": 0,
        "wallet": os.getenv("ETHEREUM_WALLET_ADDRESS"),
        "execution_network": "Multichain",
        "pricing_source": "Pool",
        "chains": {},
    }),
]:
    p = Path(fpath)
    if not p.exists():
        with open(p, "w") as f:
            json.dump(default, f)


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [] if "trades" in str(path) else {}


# -- Existing endpoints (kept for backward compat) --

@app.route('/api/trades', methods=['GET'])
def get_trades():
    """Get all executed trades."""
    return jsonify({"trades": _read_json(TRADES_FILE)})


@app.route('/api/wallet', methods=['GET'])
def get_wallet():
    """Get wallet balance info."""
    return jsonify(_read_json(WALLET_FILE))


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """Single-token dashboard data (legacy compat)."""
    trades = _read_json(TRADES_FILE)
    wallet = _read_json(WALLET_FILE)

    executed = [t for t in trades if t.get('status') == 'EXECUTED']
    buys = [t for t in executed if t['type'] == 'BUY']
    sells = [t for t in executed if t['type'] == 'SELL']

    total_profit = sum(t.get('profit', 0) for t in executed)
    win_count = len([t for t in executed if t.get('profit', 0) > 0])
    total_trades = len(executed)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    return jsonify({
        "summary": {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_profit,
            "active_positions": len(buys) - len(sells),
        },
        "wallet": wallet,
        "trades": executed[:50],
    })


@app.route('/api/trade', methods=['POST'])
def record_trade():
    """Record a new trade (called by trader)."""
    data = request.json
    trades = _read_json(TRADES_FILE)

    trade = {
        "timestamp": datetime.now().isoformat(),
        "type": data.get("type"),
        "token": data.get("token"),
        "symbol": data.get("symbol"),
        "price": data.get("price"),
        "amount": data.get("amount"),
        "profit": data.get("profit", 0),
        "gas_eth": data.get("gas_eth", 0),
        "gas_usd": data.get("gas_usd", 0),
        "tx_hash": data.get("tx_hash"),
        "chain_id": data.get("chain_id"),
        "execution_network": data.get("execution_network"),
        "status": "EXECUTED",
    }
    if data.get("usdc_received") is not None:
        trade["usdc_received"] = data["usdc_received"]

    trades.append(trade)
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

    return jsonify({"success": True, "trade": trade})


# -- New multi-token endpoints --

@app.route('/api/tokens', methods=['GET'])
def get_tokens():
    """Get all discovered tokens with pool info."""
    chain = request.args.get('chain')
    tokens = registry.get_tokens_with_pools(chain=chain)
    return jsonify({"tokens": tokens})


@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get all open positions across all tokens."""
    # If state file has the full position objects
    result = []
    raw_positions = _read_json(STATE_FILE)
    pos_data = raw_positions.get("positions", {})

    for token_addr, pos_list in pos_data.items():
        if isinstance(pos_list, list):
            for pos in pos_list:
                chain_id = pos.get('chain_id')
                if not chain_id and ':' in token_addr:
                    chain_id = int(token_addr.split(':')[0])
                chain_name = CHAINS.get(chain_id, {}).get(
                    'name', '') if chain_id else ''
                result.append({
                    "token": token_addr,
                    "symbol": pos.get("symbol", token_addr[:8]),
                    "entry_price_usd": pos.get(
                        "entry_price_usd",
                        pos.get("entry_price", 0)),
                    "amount": pos.get("amount", 0),
                    "value_usd": pos.get("value_usd", 0),
                    "decimals": pos.get("decimals", 18),
                    "chain_id": chain_id,
                    "chain_name": chain_name,
                    "timestamp": pos.get("timestamp"),
                })

    return jsonify({"positions": result, "count": len(result)})


@app.route('/api/dashboard-multi', methods=['GET'])
def get_dashboard_multi():
    """Aggregated multi-token dashboard data."""
    trades = _read_json(TRADES_FILE)
    wallet = _read_json(WALLET_FILE)
    state = _read_json(STATE_FILE)

    executed = [t for t in trades if t.get('status') == 'EXECUTED']
    total_profit = sum(t.get('profit', 0) for t in executed)
    win_count = len([t for t in executed if t.get('profit', 0) > 0])
    total_trades = len(executed)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    # Positions from state file
    pos_data = state.get("positions", {})
    total_positions = 0
    positions_by_token = {}
    for token_addr, pos_list in pos_data.items():
        if isinstance(pos_list, list):
            total_positions += len(pos_list)
            positions_by_token[token_addr] = pos_list
        elif isinstance(pos_list, int):
            total_positions += pos_list

    # Discovered tokens from registry
    tokens = registry.get_tokens_with_pools()

    # Group trades by token for per-token PnL
    pnl_by_token = {}
    for t in executed:
        tok = t.get("token") or t.get("symbol", "unknown")
        pnl_by_token.setdefault(tok, 0)
        pnl_by_token[tok] += t.get("profit", 0)

    # Recent completed round-trips (SELL trades with realized PnL)
    completed = [t for t in executed if t['type'] == 'SELL']

    # Emergency status
    stop_active = os.path.exists(STOP_FLAG)
    sell_all_active = os.path.exists(SELL_ALL_FLAG)

    return jsonify({
        "summary": {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_profit,
            "active_positions": total_positions,
            "active_tokens": len([t for t in tokens if t.get("pool_address")]),
            "discovered_tokens": len(tokens),
        },
        "wallet": wallet,
        "tokens": tokens,
        "positions": positions_by_token,
        "pnl_by_token": pnl_by_token,
        "trades": executed[:50],
        "completed_trades": completed[:30],
        "emergency": {
            "stop_active": stop_active,
            "sell_all_active": sell_all_active,
        },
    })


# -- Emergency controls --

@app.route('/api/emergency-stop', methods=['POST'])
def emergency_stop():
    """Write stop flag — trader exits loop on next iteration."""
    Path(STOP_FLAG).touch()
    return jsonify({
        "success": True,
        "message": "STOP flag set. Trader will halt on next loop iteration.",
    })


@app.route('/api/sell-all', methods=['POST'])
def sell_all():
    """Write sell-all flag — trader liquidates all positions to USDC."""
    Path(SELL_ALL_FLAG).touch()
    return jsonify({
        "success": True,
        "message": "SELL ALL flag set. Trader will liquidate all positions.",
    })


@app.route('/api/clear-stop', methods=['POST'])
def clear_stop():
    """Remove stop flag so trader can be restarted."""
    try:
        os.remove(STOP_FLAG)
    except FileNotFoundError:
        pass
    return jsonify({"success": True, "message": "STOP flag cleared."})


@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({
        "status": "ok",
        "server": "bot-api-multi",
        "stop_flag": os.path.exists(STOP_FLAG),
        "sell_all_flag": os.path.exists(SELL_ALL_FLAG),
    })


# -- Whitelist endpoints --

@app.route('/api/whitelist/senders', methods=['GET'])
def get_whitelist_senders():
    """Get all whitelisted sender addresses."""
    senders = whitelist.get_all_senders()
    return jsonify({"senders": senders})


@app.route('/api/whitelist/senders', methods=['POST'])
def add_whitelist_sender():
    """Add a whitelisted sender address."""
    data = request.json
    addr = data.get('address', '').strip()
    label = data.get('label', '')
    if not addr:
        return jsonify({"error": "address required"}), 400
    whitelist.add_sender(addr, label=label)
    return jsonify({"success": True, "address": addr, "label": label})


@app.route('/api/whitelist/tokens', methods=['GET'])
def get_whitelist_tokens():
    """Get all whitelisted tokens."""
    status = request.args.get('status')
    if status == 'pending':
        tokens = whitelist.get_pending_tokens()
    elif status == 'active':
        tokens = whitelist.get_active_tokens()
    else:
        tokens = whitelist.get_all_tokens()
    return jsonify({"tokens": tokens})


if __name__ == '__main__':
    print("""
╔════════════════════════════════════════════════════════════╗
║      MULTI-TOKEN BOT API SERVER — LOCALHOST:4000          ║
╚════════════════════════════════════════════════════════════╝

  Endpoints:
   GET  /api/trades          All trades
   GET  /api/wallet          Wallet balances
   GET  /api/dashboard       Legacy single-token dashboard
   GET  /api/dashboard-multi Multi-token dashboard data
   GET  /api/tokens          Discovered tokens + pools
   GET  /api/positions       Open positions across all tokens
   POST /api/trade           Record trade (from trader)
   POST /api/emergency-stop  STOP the trader
   POST /api/sell-all        Liquidate all positions to USDC
   POST /api/clear-stop      Clear stop flag for restart
   GET  /health              Health check

  Dashboard: http://localhost:4000/api/dashboard-multi
    """)

    app.run(host='0.0.0.0', port=4000, debug=False)
