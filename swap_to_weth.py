#!/usr/bin/env python3
"""Execute REAL swap: ETH -> WETH on Uniswap Sepolia"""

import os
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

load_dotenv(Path("/home/sauly/hummingbot/.env.local"))

rpc_url = os.getenv("ALCHEMY_RPC_URL")
private_key = os.getenv("ETHEREUM_PRIVATE_KEY")
wallet = os.getenv("ETHEREUM_WALLET_ADDRESS")

w3 = Web3(Web3.HTTPProvider(rpc_url))
account = Account.from_key(private_key)

# WETH contract on Sepolia
WETH_SEPOLIA = "0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9"

# WETH ABI (deposit function)
WETH_ABI = [
    {
        "constant": False,
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "payable": True,
        "stateMutability": "payable",
        "type": "function"
    }
]

print("""
╔═══════════════════════════════════════════════════════════╗
║         🔄 REAL SWAP: ETH -> WETH on Sepolia             ║
╚═══════════════════════════════════════════════════════════╝
""")

print(f"Wallet:     {wallet}")
print(f"WETH Address: {WETH_SEPOLIA}")
print()

try:
    # Get nonce
    nonce = w3.eth.get_transaction_count(account.address)

    # Contract
    contract = w3.eth.contract(address=WETH_SEPOLIA, abi=WETH_ABI)

    # Deposit 0.2 ETH
    amount = w3.to_wei(0.2, 'ether')

    print(f"💰 Swapping 0.2 ETH -> WETH")
    print()

    # Build transaction
    tx = contract.functions.deposit().build_transaction({
        'from': account.address,
        'value': amount,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })

    print(f"📊 Transaction Details:")
    print(f"   To: {tx['to']}")
    print(f"   Value: {amount / 1e18:.6f} ETH")
    print(f"   Gas: {tx['gas']}")
    print(f"   Gas Price: {tx['gasPrice'] / 1e9:.2f} Gwei")
    print()

    # Sign
    signed_tx = account.sign_transaction(tx)

    # Send
    print("⏳ Sending transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    print(f"✅ Transaction sent!")
    print(f"   Hash: {tx_hash.hex()}")
    print()

    # Wait for confirmation
    print("⏳ Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt['status'] == 1:
        print(f"✅ SWAP SUCCESSFUL!")
        print(f"   Block: {receipt['blockNumber']}")
        print(f"   Gas Used: {receipt['gasUsed']}")
        print()
        print(f"🎉 You now have WETH!")
        print(f"   View on Sepolia: https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
    else:
        print(f"❌ Transaction failed")

except Exception as e:
    print(f"Error: {e}")
    print()
    print("MANUAL SWAP:")
    print("1. Go to: https://app.uniswap.org/")
    print("2. Select Sepolia network")
    print("3. Swap 0.2 ETH -> WETH")
    print("4. After swap, bot will start trading!")
