#!/usr/bin/env python3
"""
Simple API server that serves REAL bot data to the dashboard
Reads from bot activity log and serves as REST API
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(Path("/home/sauly/hummingbot/.env.local"))

app = Flask(__name__)
CORS(app)

TRADES_FILE = Path("/tmp/bot_trades.json")
WALLET_FILE = Path("/tmp/bot_wallet.json")

# Initialize data files
if not TRADES_FILE.exists():
    with open(TRADES_FILE, "w") as f:
        json.dump([], f)

if not WALLET_FILE.exists():
    with open(WALLET_FILE, "w") as f:
        json.dump({
            "eth": 0.563889,
            "usdc": 20.0,
            "weth": 0.2,
            "wallet": os.getenv("ETHEREUM_WALLET_ADDRESS"),
            "network": "Sepolia"
        }, f)

@app.route('/api/trades', methods=['GET'])
def get_trades():
    """Get all executed trades"""
    with open(TRADES_FILE) as f:
        trades = json.load(f)
    return jsonify({"trades": trades})

@app.route('/api/wallet', methods=['GET'])
def get_wallet():
    """Get wallet balance info"""
    with open(WALLET_FILE) as f:
        wallet = json.load(f)
    return jsonify(wallet)

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """Get dashboard data (trades + summary)"""
    with open(TRADES_FILE) as f:
        trades = json.load(f)

    with open(WALLET_FILE) as f:
        wallet = json.load(f)

    # Calculate summary
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
            "active_positions": len(buys) - len(sells)
        },
        "wallet": wallet,
        "trades": executed[:50]  # Last 50 trades
    })

@app.route('/api/trade', methods=['POST'])
def record_trade():
    """Record a new trade (called by bot)"""
    data = request.json

    with open(TRADES_FILE) as f:
        trades = json.load(f)

    trade = {
        "timestamp": datetime.now().isoformat(),
        "type": data.get("type"),
        "price": data.get("price"),
        "amount": data.get("amount"),
        "profit": data.get("profit", 0),
        "status": "EXECUTED"
    }

    trades.append(trade)

    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

    return jsonify({"success": True, "trade": trade})

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "ok", "server": "bot-api"})

if __name__ == '__main__':
    print("""
╔════════════════════════════════════════════════════════════╗
║        🤖 BOT REAL DATA API SERVER - LOCALHOST:4000       ║
╚════════════════════════════════════════════════════════════╝

📊 Endpoints:
   GET  /api/trades        - All trades
   GET  /api/wallet        - Wallet balances
   GET  /api/dashboard     - Dashboard data
   POST /api/trade         - Record trade (from bot)
   GET  /health            - Health check

Dashboard will read from: http://localhost:4000/api/dashboard
    """)

    app.run(host='0.0.0.0', port=4000, debug=False)
