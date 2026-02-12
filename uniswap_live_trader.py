#!/usr/bin/env python3
"""
🚀 LIVE UNISWAP TRADER - Real Blockchain Execution
Executes actual swaps on Ethereum Sepolia 24/7
Using SEPOLIA prices from the EXACT POOL being traded
"""

import os
import sys
import time
import requests
import json
import asyncio
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

# Load config
load_dotenv(Path("/home/sauly/hummingbot/.env.local"))
load_dotenv(Path("/home/sauly/hummingbot/mcp/.env"))

# Setup
RPC_URL = os.getenv("ALCHEMY_RPC_URL")
PRIVATE_KEY = os.getenv("ETHEREUM_PRIVATE_KEY")
WALLET = os.getenv("ETHEREUM_WALLET_ADDRESS")
API_SERVER = "http://localhost:4000"

# Uniswap on Sepolia (Execution & Pricing)
WETH = "0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9"
USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
QUOTER_V2 = "0xEd1f6473345F45b75F8179591dd5bA1888cf2FB3"

# Trading config
# We use the 1% fee tier (10000) because that's where liquidity is on Sepolia
FEE_TIER = 10000 
POSITION_SIZE = 0.05  # WETH per trade
TAKE_PROFIT = 1.04   # 4%
STOP_LOSS = 0.975    # 2.5%

# Uniswap V3 SwapRouter ABI
ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "internalType": "struct ISwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "refundETH",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]

# ERC20 ABI
ERC20_ABI = [
    {
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Uniswap V3 QuoterV2 ABI
QUOTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "sqrtPriceX96After", "type": "uint160"},
            {"name": "initializedTicksCrossed", "type": "uint32"},
            {"name": "gasEstimate", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Token decimals cache
TOKEN_DECIMALS = {}

class UniswapLiveTrader:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.account = Account.from_key(PRIVATE_KEY)
        self.positions = {}
        self.trades = []

        if not self.w3.is_connected():
            print("❌ Cannot connect to RPC")
            sys.exit(1)

        print(f"✅ Connected to Sepolia")
        print(f"   Wallet: {self.account.address}")
        print(f"   RPC: {RPC_URL.split('/')[-1]}...")
        print(f"   Pool: WETH/USDC (Fee: {FEE_TIER/10000:.2f}%)")

    def get_gas_params(self):
        """Get EIP-1559 gas parameters suitable for Sepolia"""
        try:
            latest = self.w3.eth.get_block('latest')
            base_fee = latest.get('baseFeePerGas', self.w3.eth.gas_price)
            max_priority = self.w3.to_wei(2, 'gwei')
            max_fee = base_fee * 2 + max_priority
            return {
                'maxFeePerGas': max_fee,
                'maxPriorityFeePerGas': max_priority,
            }
        except Exception:
            return {'gasPrice': self.w3.eth.gas_price * 2}

    def get_nonce(self):
        return self.w3.eth.get_transaction_count(self.account.address, 'pending')

    def get_price(self, amount_weth=1.0):
        """Get WETH/USDC price from using the EXACT SAME params as execution"""
        try:
            quoter = self.w3.eth.contract(address=QUOTER_V2, abi=QUOTER_ABI)
            amount_in = int(amount_weth * 1e18)

            # Using Sepolia WETH, Sepolia USDC, and the trading FEE_TIER
            result = quoter.functions.quoteExactInputSingle({
                'tokenIn': WETH,
                'tokenOut': USDC,
                'amountIn': amount_in,
                'fee': FEE_TIER,
                'sqrtPriceLimitX96': 0
            }).call()

            amount_out = result[0]
            price = amount_out / 1e6 / amount_weth
            return price
        except Exception as e:
            print(f"⚠️  Price fetch error: {e}")
            return None

    def get_decimals(self, token_addr):
        if token_addr not in TOKEN_DECIMALS:
            contract = self.w3.eth.contract(address=token_addr, abi=ERC20_ABI)
            TOKEN_DECIMALS[token_addr] = contract.functions.decimals().call()
        return TOKEN_DECIMALS[token_addr]

    def get_balance(self, token_addr):
        try:
            contract = self.w3.eth.contract(address=token_addr, abi=ERC20_ABI)
            balance = contract.functions.balanceOf(self.account.address).call()
            decimals = self.get_decimals(token_addr)
            return balance / (10 ** decimals)
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0

    def approve_token(self, token_addr, amount_wei):
        try:
            contract = self.w3.eth.contract(address=token_addr, abi=ERC20_ABI)
            gas_params = self.get_gas_params()
            tx = contract.functions.approve(ROUTER, amount_wei).build_transaction({
                'from': self.account.address,
                'nonce': self.get_nonce(),
                'gas': 100000,
                **gas_params,
            })

            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"✅ Token approved: {tx_hash.hex()[:16]}...")
                return True
            return False
        except Exception as e:
            print(f"⚠️  Approval error: {e}")
            return False

    def swap_weth_to_usdc(self, amount_weth):
        """Execute swap on Sepolia using the configured FEE_TIER"""
        try:
            amount_wei = int(amount_weth * 1e18)

            print(f"📝 Approving {amount_weth} WETH...")
            if not self.approve_token(WETH, amount_wei):
                return None

            router = self.w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)
            gas_params = self.get_gas_params()
            deadline = int(time.time()) + 300

            tx = router.functions.exactInputSingle({
                'tokenIn': WETH,
                'tokenOut': USDC,
                'fee': FEE_TIER,
                'recipient': self.account.address,
                'deadline': deadline,
                'amountIn': amount_wei,
                'amountOutMinimum': 0,
                'sqrtPriceLimitX96': 0
            }).build_transaction({
                'from': self.account.address,
                'nonce': self.get_nonce(),
                'gas': 300000,
                **gas_params,
            })

            print(f"🔄 Executing swap: {amount_weth} WETH → USDC (Fee: {FEE_TIER})")
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

            print(f"⏳ Confirming transaction: {tx_hash.hex()[:16]}...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"✅ SWAP SUCCESSFUL!")
                print(f"   TX: {tx_hash.hex()}")
                return {
                    'tx': tx_hash.hex(),
                    'amount': amount_weth,
                    'status': 'success'
                }
            else:
                print(f"❌ Swap failed on-chain")
                return None

        except Exception as e:
            print(f"❌ Swap error: {e}")
            return None

    def record_trade(self, trade_type, price, amount, profit=0):
        try:
            response = requests.post(
                f"{API_SERVER}/api/trade",
                json={
                    "type": trade_type,
                    "price": price,
                    "amount": amount,
                    "profit": profit
                },
                timeout=5
            )
            if response.status_code == 200:
                print(f"✅ Trade recorded: {trade_type}")
                return True
        except Exception:
            pass
        return False

    def sync_wallet_data(self, block_number=None):
        try:
            eth_bal = float(self.w3.from_wei(
                self.w3.eth.get_balance(self.account.address), 'ether'))
            weth_bal = self.get_balance(WETH)
            usdc_bal = self.get_balance(USDC)

            wallet_data = {
                "eth": round(eth_bal, 6),
                "weth": round(weth_bal, 6),
                "usdc": round(usdc_bal, 6),
                "wallet": self.account.address,
                "network": "Sepolia",
                "block": block_number,
                "updated": datetime.now().isoformat()
            }
            with open("/tmp/bot_wallet.json", "w") as f:
                json.dump(wallet_data, f, indent=2)
            return eth_bal, weth_bal, usdc_bal
        except Exception as e:
            print(f"⚠️  Wallet sync error: {e}")
            return None, None, None

    async def run(self):
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║   🚀 LIVE TRADER - SEPOLIA EXECUTION & PRICING           ║
║       Using the EXACT POOL we trade on for prices         ║
╚═══════════════════════════════════════════════════════════╝

⚙️  Configuration:
   Position Size: {POSITION_SIZE} WETH
   Fee Tier: {FEE_TIER/10000:.2f}%
   Network: Sepolia
   Pricing: Sepolia (Same Pool)
   Wallet: {self.account.address}

📊 Dashboard: http://localhost:3000/dashboard.html
""")

        eth_bal, weth_bal, usdc_bal = self.sync_wallet_data()
        current_price = self.get_price(1.0)

        print(f"💰 Starting Balances:")
        print(f"   ETH:  {eth_bal:.6f}")
        print(f"   WETH: {weth_bal:.6f}")
        print(f"   USDC: {usdc_bal:.6f}")
        if current_price:
            print(f"   Price: ${current_price:.2f}")
        
        if weth_bal < POSITION_SIZE:
            print(f"⚠️  Insufficient WETH to trade")
            return

        print("✅ Starting loop...")
        
        start_time = time.time()
        trade_count = 0
        buy_price = None
        in_position = False
        last_block = self.w3.eth.block_number
        blocks_since_signal = 0
        signal_interval = 20

        try:
            while True:
                current_block = self.w3.eth.block_number
                if current_block <= last_block:
                    await asyncio.sleep(2)
                    continue

                new_blocks = current_block - last_block
                last_block = current_block
                blocks_since_signal += new_blocks
                elapsed = (time.time() - start_time) / 3600

                _, weth_bal, usdc_bal = self.sync_wallet_data(current_block)
                current_price = self.get_price(1.0)

                if current_block % 10 == 0:
                     print(f"[{datetime.now().strftime('%H:%M:%S')}] Block {current_block} | Price: ${current_price:.2f} | WETH: {weth_bal:.6f}")

                if blocks_since_signal >= signal_interval and current_price is not None:
                    blocks_since_signal = 0
                    
                    if not in_position:
                        print(f"🟢 BUY SIGNAL at ${current_price:.2f}")
                        if self.swap_weth_to_usdc(POSITION_SIZE):
                            in_position = True
                            buy_price = current_price
                            trade_count += 1
                            self.record_trade("BUY", buy_price, POSITION_SIZE, 0)
                    
                    elif in_position:
                        change = current_price / buy_price
                        if change >= TAKE_PROFIT:
                            profit = (current_price - buy_price) * POSITION_SIZE
                            print(f"💰 TAKE PROFIT at ${current_price:.2f}")
                            self.record_trade("SELL", current_price, POSITION_SIZE, profit)
                            in_position = False
                            trade_count += 1
                        elif change <= STOP_LOSS:
                            loss = (current_price - buy_price) * POSITION_SIZE
                            print(f"🛑 STOP LOSS at ${current_price:.2f}")
                            self.record_trade("SELL", current_price, POSITION_SIZE, loss)
                            in_position = False
                            trade_count += 1

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            self.print_summary(trade_count)

    def print_summary(self, count):
        print(f"\nStopped. Total Trades: {count}")

async def main():
    trader = UniswapLiveTrader()
    await trader.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
