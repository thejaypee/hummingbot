#!/usr/bin/env python3
"""
LIVE UNISWAP TRADER - Dual-Chain Architecture
  Pricing:   Ethereum Mainnet Uniswap V3 (real market prices)
  Execution: Base Sepolia Uniswap V3 (testnet swaps, no capital risk)
  PnL:       Calculated from Mainnet prices for realistic performance tracking
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

load_dotenv(Path("/home/sauly/hummingbot/.env.local"))
load_dotenv(Path("/home/sauly/hummingbot/mcp/.env"))

# RPC endpoints
TESTNET_RPC = os.getenv("TESTNET_RPC_URL")
MAINNET_RPC = os.getenv("MAINNET_RPC_URL")
PRIVATE_KEY = os.getenv("ETHEREUM_PRIVATE_KEY")
API_SERVER = "http://localhost:4000"

# --- Mainnet Contracts (Pricing Layer) ---
MAINNET_WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
MAINNET_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
MAINNET_QUOTER_V2 = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
MAINNET_FEE_TIER = 500  # 0.05% deepest WETH/USDC liquidity

# --- Base Sepolia Contracts (Execution Layer) ---
TESTNET_WETH = "0x4200000000000000000000000000000000000006"
TESTNET_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
TESTNET_ROUTER = "0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4"
TESTNET_FEE_TIER = 3000  # 0.30% deepest Base Sepolia WETH/USDC liquidity
TESTNET_CHAIN_ID = 84532
TESTNET_NAME = "Base Sepolia"

# Trading config
POSITION_SIZE = 0.01  # WETH per trade (conservative for testnet)
TAKE_PROFIT = 1.001   # 0.1% — very tight for active testing
STOP_LOSS = 0.999     # 0.1% — very tight for active testing

# SwapRouter02 ABI (no deadline in struct)
ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "recipient", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMinimum", "type": "uint256"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
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
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

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


class UniswapLiveTrader:
    def __init__(self):
        self.w3_mainnet = Web3(Web3.HTTPProvider(MAINNET_RPC))
        self.w3_testnet = Web3(Web3.HTTPProvider(TESTNET_RPC))
        self.account = Account.from_key(PRIVATE_KEY)
        self.total_pnl = 0.0
        self.trade_count = 0

        if not self.w3_mainnet.is_connected():
            print("Cannot connect to Mainnet RPC")
            sys.exit(1)
        if not self.w3_testnet.is_connected():
            print(f"Cannot connect to {TESTNET_NAME} RPC")
            sys.exit(1)

        mainnet_chain = self.w3_mainnet.eth.chain_id
        testnet_chain = self.w3_testnet.eth.chain_id
        if mainnet_chain != 1:
            print(
                f"Mainnet RPC returned chain_id {mainnet_chain}, "
                f"expected 1")
            sys.exit(1)
        if testnet_chain != TESTNET_CHAIN_ID:
            print(
                f"Testnet RPC returned chain_id {testnet_chain}, "
                f"expected {TESTNET_CHAIN_ID}")
            sys.exit(1)

        self.mainnet_quoter = self.w3_mainnet.eth.contract(
            address=MAINNET_QUOTER_V2, abi=QUOTER_ABI)
        self.testnet_router = self.w3_testnet.eth.contract(
            address=TESTNET_ROUTER, abi=ROUTER_ABI)

        print(f"Connected | Mainnet (pricing) + {TESTNET_NAME} (execution)")
        print(f"  Wallet:  {self.account.address}")
        print(
            f"  Pricing: Mainnet WETH/USDC "
            f"{MAINNET_FEE_TIER / 10000:.2f}% pool")
        print(
            f"  Swaps:   {TESTNET_NAME} WETH/USDC "
            f"{TESTNET_FEE_TIER / 10000:.2f}% pool")

    # -- Pricing (Mainnet) -------------------------------------------------

    def get_mainnet_price(self, amount_weth=1.0):
        try:
            amount_in = int(amount_weth * 1e18)
            result = self.mainnet_quoter.functions.quoteExactInputSingle({
                'tokenIn': MAINNET_WETH,
                'tokenOut': MAINNET_USDC,
                'amountIn': amount_in,
                'fee': MAINNET_FEE_TIER,
                'sqrtPriceLimitX96': 0
            }).call()
            return result[0] / 1e6 / amount_weth
        except Exception as e:
            print(f"  Mainnet price error: {e}")
            return None

    # -- Execution helpers (Base Sepolia) -----------------------------------

    def get_gas_params(self):
        try:
            latest = self.w3_testnet.eth.get_block('latest')
            base_fee = latest.get(
                'baseFeePerGas', self.w3_testnet.eth.gas_price)
            max_priority = self.w3_testnet.to_wei(1, 'gwei')
            max_fee = base_fee * 2 + max_priority
            return {
                'maxFeePerGas': max_fee,
                'maxPriorityFeePerGas': max_priority
            }
        except Exception:
            return {'gasPrice': self.w3_testnet.eth.gas_price * 2}

    def get_nonce(self):
        return self.w3_testnet.eth.get_transaction_count(
            self.account.address, 'pending')

    def get_balance(self, token_addr):
        try:
            contract = self.w3_testnet.eth.contract(
                address=token_addr, abi=ERC20_ABI)
            decimals = contract.functions.decimals().call()
            balance = contract.functions.balanceOf(
                self.account.address).call()
            return balance / (10 ** decimals)
        except Exception as e:
            print(f"  Balance error: {e}")
            return 0.0

    def ensure_approval(self, token_addr, amount_wei):
        contract = self.w3_testnet.eth.contract(
            address=token_addr, abi=ERC20_ABI)
        current = contract.functions.allowance(
            self.account.address, TESTNET_ROUTER).call()
        if current >= amount_wei:
            return True
        try:
            gas_params = self.get_gas_params()
            tx = contract.functions.approve(
                TESTNET_ROUTER, 2**256 - 1
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.get_nonce(),
                'gas': 100000,
                **gas_params,
            })
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3_testnet.eth.send_raw_transaction(
                signed.raw_transaction)
            receipt = self.w3_testnet.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120)
            if receipt['status'] == 1:
                print(f"  Approved: {tx_hash.hex()[:16]}...")
                return True
            print("  Approval failed on-chain")
            return False
        except Exception as e:
            print(f"  Approval error: {e}")
            return False

    # -- Swaps (Base Sepolia) -----------------------------------------------

    def _execute_swap(self, token_in, token_out, amount_in_wei, label):
        """Returns (tx_hash, gas_cost_eth) or (None, 0)."""
        if not self.ensure_approval(token_in, amount_in_wei):
            return None, 0
        try:
            gas_params = self.get_gas_params()
            tx = self.testnet_router.functions.exactInputSingle({
                'tokenIn': token_in,
                'tokenOut': token_out,
                'fee': TESTNET_FEE_TIER,
                'recipient': self.account.address,
                'amountIn': amount_in_wei,
                'amountOutMinimum': 0,
                'sqrtPriceLimitX96': 0
            }).build_transaction({
                'from': self.account.address,
                'nonce': self.get_nonce(),
                'gas': 600000,
                **gas_params,
            })
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3_testnet.eth.send_raw_transaction(
                signed.raw_transaction)
            print(f"  {label} tx sent: {tx_hash.hex()[:16]}...")
            receipt = self.w3_testnet.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120)
            if receipt['status'] == 1:
                gas_cost_wei = (receipt['gasUsed']
                                * receipt['effectiveGasPrice'])
                gas_cost_eth = float(self.w3_testnet.from_wei(
                    gas_cost_wei, 'ether'))
                print(
                    f"  {label} confirmed "
                    f"(gas: {receipt['gasUsed']} units, "
                    f"{gas_cost_eth:.6f} ETH)")
                return tx_hash.hex(), gas_cost_eth
            print(f"  {label} reverted on-chain")
            return None, 0
        except Exception as e:
            print(f"  {label} error: {e}")
            return None, 0

    def swap_weth_to_usdc(self, amount_weth):
        amount_wei = int(amount_weth * 1e18)
        return self._execute_swap(
            TESTNET_WETH, TESTNET_USDC, amount_wei, "WETH->USDC")

    def swap_usdc_to_weth(self, amount_usdc):
        amount_wei = int(amount_usdc * 1e6)
        return self._execute_swap(
            TESTNET_USDC, TESTNET_WETH, amount_wei, "USDC->WETH")

    def gas_cost_usd(self, gas_eth, mainnet_price):
        """Convert gas cost in ETH to USD using Mainnet price."""
        return gas_eth * mainnet_price

    # -- Data sync ----------------------------------------------------------

    def record_trade(self, trade_type, mainnet_price, amount,
                     profit=0, tx_hash=None, usdc_received=None):
        try:
            payload = {
                "type": trade_type,
                "price": mainnet_price,
                "amount": amount,
                "profit": profit,
                "tx_hash": tx_hash,
                "execution_network": TESTNET_NAME,
                "pricing_source": "mainnet",
            }
            if usdc_received is not None:
                payload["usdc_received"] = usdc_received
            requests.post(
                f"{API_SERVER}/api/trade",
                json=payload,
                timeout=5
            )
        except Exception:
            pass

    def sync_wallet_data(self, block_number=None, mainnet_price=None):
        try:
            eth_bal = float(self.w3_testnet.from_wei(
                self.w3_testnet.eth.get_balance(self.account.address),
                'ether'))
            weth_bal = self.get_balance(TESTNET_WETH)
            usdc_bal = self.get_balance(TESTNET_USDC)

            wallet_data = {
                "eth": round(eth_bal, 6),
                "weth": round(weth_bal, 6),
                "usdc": round(usdc_bal, 6),
                "wallet": self.account.address,
                "execution_network": TESTNET_NAME,
                "pricing_source": "Mainnet",
                "mainnet_price": (
                    round(mainnet_price, 2) if mainnet_price else None),
                "total_pnl": round(self.total_pnl, 4),
                "block": block_number,
                "updated": datetime.now().isoformat()
            }
            with open("/tmp/bot_wallet.json", "w") as f:
                json.dump(wallet_data, f, indent=2)
            return eth_bal, weth_bal, usdc_bal
        except Exception as e:
            print(f"  Wallet sync error: {e}")
            return None, None, None

    # -- Main loop ----------------------------------------------------------

    async def run(self):
        mainnet_price = self.get_mainnet_price(1.0)
        eth_bal, weth_bal, usdc_bal = self.sync_wallet_data(
            mainnet_price=mainnet_price)

        print(f"""
========================================================
  LIVE TRADER | Mainnet Pricing + {TESTNET_NAME} Execution
========================================================
  Position Size : {POSITION_SIZE} WETH
  Take Profit   : {(TAKE_PROFIT - 1) * 100:.1f}%
  Stop Loss     : {(1 - STOP_LOSS) * 100:.1f}%
  Pricing Pool  : Mainnet WETH/USDC ({MAINNET_FEE_TIER / 10000:.2f}%)
  Execution Pool: {TESTNET_NAME} WETH/USDC ({TESTNET_FEE_TIER / 10000:.2f}%)
  Wallet        : {self.account.address}
--------------------------------------------------------
  ETH  : {eth_bal:.6f}
  WETH : {weth_bal:.6f}
  USDC : {usdc_bal:.6f}
  Price: ${mainnet_price:.2f} (Mainnet)
--------------------------------------------------------
  API Server : {API_SERVER}
========================================================
""")

        # Restore open positions from trade history
        open_positions = []
        try:
            with open("/tmp/bot_trades.json") as f:
                trades = json.load(f)
            buys = [t for t in trades if t['type'] == 'BUY']
            sells = [t for t in trades if t['type'] == 'SELL']
            unmatched = len(buys) - len(sells)
            if unmatched > 0:
                for b in buys[-unmatched:]:
                    open_positions.append({
                        "entry_price": b["price"],
                        "amount": b["amount"],
                        "usdc_held": b.get("usdc_received",
                                           b["amount"] * b["price"])
                    })
                print(f"  Restored {len(open_positions)} open positions:")
                for p in open_positions:
                    print(f"    entry ${p['entry_price']:.2f} "
                          f"x {p['amount']} WETH "
                          f"({p['usdc_held']:.2f} USDC)")
                self.total_pnl = sum(
                    t.get('profit', 0) for t in trades)
        except Exception:
            pass

        last_block = self.w3_testnet.eth.block_number
        blocks_since_signal = 0
        signal_interval = 5  # check every ~10s for active testing

        print("Starting trading loop...")

        error_count = 0
        max_backoff = 60

        while True:
            try:
                current_block = self.w3_testnet.eth.block_number
                error_count = 0  # reset on success

                if current_block <= last_block:
                    await asyncio.sleep(2)
                    continue

                new_blocks = current_block - last_block
                last_block = current_block
                blocks_since_signal += new_blocks

                mainnet_price = self.get_mainnet_price(1.0)
                if mainnet_price is None:
                    await asyncio.sleep(2)
                    continue

                _, weth_bal, usdc_bal = self.sync_wallet_data(
                    current_block, mainnet_price)

                if current_block % 10 == 0:
                    n = len(open_positions)
                    status = f"{n} POS" if n > 0 else "IDLE"
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"Block {current_block} | "
                        f"${mainnet_price:.2f} (Mainnet) | "
                        f"WETH: {weth_bal:.4f} | "
                        f"USDC: {usdc_bal:.2f} | "
                        f"PnL: ${self.total_pnl:.4f} | "
                        f"{status}")

                # Check exits — each position independently
                closed = []
                for i, pos in enumerate(open_positions):
                    change = mainnet_price / pos["entry_price"]
                    if change >= TAKE_PROFIT or change <= STOP_LOSS:
                        # Gross PnL from price movement
                        gross_pnl = ((mainnet_price - pos["entry_price"])
                                     * pos["amount"])
                        tag = ("TAKE PROFIT" if change >= TAKE_PROFIT
                               else "STOP LOSS")

                        # Swap only THIS position's USDC
                        tx = None
                        gas_cost = 0
                        swap_amount = pos["usdc_held"]
                        avail = self.get_balance(TESTNET_USDC)
                        if swap_amount > avail:
                            swap_amount = avail
                        if swap_amount > 0.01:
                            tx, gas_eth = self.swap_usdc_to_weth(
                                swap_amount)
                            gas_cost = self.gas_cost_usd(
                                gas_eth, mainnet_price)

                        # Total gas = entry gas + exit gas
                        total_gas = (pos.get("entry_gas_usd", 0)
                                     + gas_cost)
                        net_pnl = gross_pnl - total_gas

                        print(
                            f"  {tag} #{i + 1} at ${mainnet_price:.2f} "
                            f"(entry ${pos['entry_price']:.2f}, "
                            f"gross ${gross_pnl:.4f}, "
                            f"gas ${total_gas:.4f}, "
                            f"net ${net_pnl:.4f})")

                        self.total_pnl += net_pnl
                        self.trade_count += 1
                        self.record_trade(
                            "SELL", mainnet_price,
                            pos["amount"], net_pnl, tx)
                        closed.append(i)
                        # Re-read balance after swap
                        if tx:
                            weth_bal = self.get_balance(TESTNET_WETH)

                for i in reversed(closed):
                    open_positions.pop(i)

                # Check entry on signal interval
                if blocks_since_signal >= signal_interval:
                    blocks_since_signal = 0

                    if weth_bal >= POSITION_SIZE:
                        usdc_before = self.get_balance(TESTNET_USDC)
                        print(
                            f"  ENTER at Mainnet price "
                            f"${mainnet_price:.2f}")
                        tx, gas_eth = self.swap_weth_to_usdc(
                            POSITION_SIZE)
                        if tx:
                            entry_gas_usd = self.gas_cost_usd(
                                gas_eth, mainnet_price)
                            usdc_after = self.get_balance(TESTNET_USDC)
                            usdc_received = usdc_after - usdc_before
                            open_positions.append({
                                "entry_price": mainnet_price,
                                "amount": POSITION_SIZE,
                                "usdc_held": usdc_received,
                                "entry_gas_usd": entry_gas_usd
                            })
                            self.trade_count += 1
                            print(
                                f"  Got {usdc_received:.4f} USDC "
                                f"(gas: ${entry_gas_usd:.4f})")
                            self.record_trade(
                                "BUY", mainnet_price,
                                POSITION_SIZE, 0, tx,
                                usdc_received=usdc_received)

                await asyncio.sleep(1)

            except KeyboardInterrupt:
                print(
                    f"\nStopped. Trades: {self.trade_count} | "
                    f"Total PnL: ${self.total_pnl:.4f}")
                break

            except Exception as e:
                error_count += 1
                backoff = min(2 ** error_count, max_backoff)
                print(
                    f"  [{datetime.now().strftime('%H:%M:%S')}] "
                    f"Error (retry {error_count}, wait {backoff}s): "
                    f"{type(e).__name__}: {e}")
                await asyncio.sleep(backoff)


async def main():
    trader = UniswapLiveTrader()
    await trader.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
