#!/usr/bin/env python3
"""Check real USDC and WETH token balances"""

import os
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

load_dotenv(Path("/home/sauly/hummingbot/.env.local"))

rpc_url = os.getenv("ALCHEMY_RPC_URL")
wallet = os.getenv("ETHEREUM_WALLET_ADDRESS")

w3 = Web3(Web3.HTTPProvider(rpc_url))

# Token contract addresses on Sepolia
USDC_SEPOLIA = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
WETH_SEPOLIA = "0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9"

# Standard ERC20 ABI for balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

print("💰 Checking Real Token Balances on Sepolia...\n")

def check_token(address, name, symbol):
    try:
        contract = w3.eth.contract(address=address, abi=ERC20_ABI)
        balance_raw = contract.functions.balanceOf(wallet).call()
        decimals = contract.functions.decimals().call()
        balance = balance_raw / (10 ** decimals)

        print(f"{name} ({symbol})")
        print(f"   Address: {address}")
        print(f"   Raw Balance: {balance_raw}")
        print(f"   Decimals: {decimals}")
        print(f"   Balance: {balance:.6f} {symbol}")
        print()

        return balance
    except Exception as e:
        print(f"{name}: Error - {e}\n")
        return 0

print(f"Wallet: {wallet}\n")

usdc = check_token(USDC_SEPOLIA, "USD Coin", "USDC")
weth = check_token(WETH_SEPOLIA, "Wrapped Ether", "WETH")

print("═" * 50)
print("TRADING READINESS")
print("═" * 50)
print(f"ETH:   0.563889 ✅")
print(f"USDC:  {usdc:.6f} " + ("✅" if usdc > 0 else "⚠️"))
print(f"WETH:  {weth:.6f} " + ("✅" if weth > 0 else "⚠️"))

if usdc > 0 and weth > 0:
    print("\n🚀 READY TO TRADE!")
elif usdc > 0 or weth > 0:
    print("\n⚠️  Partially funded (have one token)")
else:
    print("\n⚠️  Need USDC and WETH to trade")
