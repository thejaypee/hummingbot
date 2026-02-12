#!/usr/bin/env python3
"""
Check REAL wallet data on Ethereum Sepolia
Actual blockchain queries, not simulation
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load actual credentials
load_dotenv(Path("/home/sauly/hummingbot/.env.local"))

wallet_address = os.getenv("ETHEREUM_WALLET_ADDRESS")
rpc_url = os.getenv("ALCHEMY_RPC_URL")
private_key = os.getenv("ETHEREUM_PRIVATE_KEY")

print("🔍 Checking REAL Wallet on Ethereum Sepolia...\n")

try:
    from web3 import Web3

    # Connect to real RPC
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print("❌ Cannot connect to RPC")
        sys.exit(1)

    print(f"✅ Connected to Ethereum Sepolia")
    print(f"   RPC: {rpc_url.split('/')[-1]}...")
    print()

    # Get real network info
    latest_block = w3.eth.block_number
    chain_id = w3.eth.chain_id

    print(f"📊 Network Status:")
    print(f"   Latest Block: {latest_block}")
    print(f"   Chain ID: {chain_id} (Sepolia = 11155111)")
    print()

    # Get REAL wallet balance
    balance_wei = w3.eth.get_balance(wallet_address)
    balance_eth = w3.from_wei(balance_wei, 'ether')

    print(f"👛 Your Wallet: {wallet_address}")
    print(f"   ETH Balance: {balance_eth:.6f} ETH")
    print(f"   Wei Balance: {balance_wei}")
    print()

    if balance_eth == 0:
        print("⚠️  WALLET EMPTY - You need Sepolia ETH to trade!")
        print("    Get free ETH: https://www.infura.io/faucet/sepolia")
    else:
        print(f"✅ Wallet funded: {balance_eth:.6f} ETH")

    # Check transaction count (proxy for account activity)
    tx_count = w3.eth.get_transaction_count(wallet_address)
    print(f"   Transactions: {tx_count}")
    print()

    # Try to get recent block data
    print(f"📈 Latest Block Data:")
    latest_block_data = w3.eth.get_block(latest_block)
    print(f"   Block Hash: {latest_block_data['hash'].hex()}")
    print(f"   Timestamp: {latest_block_data['timestamp']}")
    print(f"   Transactions: {len(latest_block_data['transactions'])}")
    print(f"   Gas Used: {latest_block_data['gasUsed']}")
    print()

    # Check if we can connect to Uniswap contract
    UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"

    print(f"🦄 Uniswap V3 Router Check:")
    print(f"   Address: {UNISWAP_V3_ROUTER}")

    router_code = w3.eth.get_code(UNISWAP_V3_ROUTER)
    if router_code and router_code != b'':
        print(f"   Status: ✅ Contract exists on Sepolia")
        print(f"   Code size: {len(router_code)} bytes")
    else:
        print(f"   Status: ❌ Contract not found or empty")

    print()
    print("═" * 60)
    print("SUMMARY: Real Sepolia Network Data")
    print("═" * 60)
    print(f"✅ Network Connection: OK")
    print(f"✅ Wallet Address: OK")
    print(f"✅ RPC Provider: OK")

    if balance_eth > 0:
        print(f"✅ Wallet Funded: {balance_eth:.6f} ETH")
        print(f"\n🚀 Ready to trade on Uniswap Sepolia!")
    else:
        print(f"⚠️  Wallet Empty: Get testnet ETH first")
        print(f"   https://www.infura.io/faucet/sepolia")

    print()

except ImportError:
    print("❌ web3.py not installed")
    print("   pip install web3")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
