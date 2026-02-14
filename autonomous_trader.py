#!/usr/bin/env python3
"""
AUTONOMOUS MULTI-TOKEN TRADER — Uniswap V4 | Multichain

Pipeline:
  1. Startup scan detects existing token balances across all chains
  2. V3 Factory pool discovery on that chain
  3. Order set via UniversalRouter V4 on the correct chain
  4. Monitor attached: TP/SL checked every block on that chain

Each chain has its own Web3 connection, router, and permit2 instance.
Positions carry chain_id metadata so the right RPC is used for exits.

Uniswap V4 swap encoding based on official docs:
  https://docs.uniswap.org/contracts/v4/quickstart/swap
  https://docs.uniswap.org/contracts/universal-router/technical-reference
  https://docs.uniswap.org/sdk/v4/reference/enumerations/Actions
"""

import asyncio
import json
import os
import queue
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from eth_abi import encode
from eth_account import Account
from web3 import Web3

from config.trading_config import (
    ACTION_SETTLE_ALL,
    ACTION_SWAP_EXACT_IN_SINGLE,
    ACTION_TAKE_ALL,
    CHAINS,
    DEFAULT_SIGNAL_INTERVAL,
    DEFAULT_STOP_LOSS,
    DEFAULT_TAKE_PROFIT,
    GAS_RESERVE_ETH,
    PERMIT2,
    SELL_ALL_FLAG,
    STATE_FILE,
    STOP_FLAG,
    V4_SWAP_COMMAND,
    WALLET_FILE,
)
from token_monitor import TokenMonitor
from token_registry import TokenRegistry
from whitelist import WhitelistManager

load_dotenv(Path("/home/sauly/hummingbot/.env.local"))
load_dotenv(Path("/home/sauly/hummingbot/mcp/.env"))

PRIVATE_KEY = os.getenv("ETHEREUM_PRIVATE_KEY")
API_SERVER = "http://localhost:4000"

# Mainnet pricing (always Ethereum mainnet QuoterV2)
MAINNET_RPC = os.getenv("MAINNET_RPC_URL")
MAINNET_QUOTER_V2 = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
MAINNET_WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
MAINNET_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
MAINNET_FEE_TIER = 500

# Testnets — skip gas profitability checks (no real value)
TESTNET_CHAINS = {84532, 421614, 11155111}

# Testnet → Mainnet chain mapping for pricing
TESTNET_TO_MAINNET = {84532: 8453, 421614: 42161, 11155111: 1}

# V3 Factory ABI — getPool(tokenA, tokenB, fee)
V3_FACTORY_ABI = [
    {
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
            {"name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

V3_FEE_TIERS = [500, 3000, 10000]

QUOTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "sqrtPriceX96After", "type": "uint160"},
            {"name": "initializedTicksCrossed", "type": "uint32"},
            {"name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Permit2 ABI — approve(token, spender, amount, expiration)
# Source: https://docs.uniswap.org/contracts/permit2/overview
PERMIT2_ABI = [
    {
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint160"},
            {"name": "expiration", "type": "uint48"},
        ],
        "name": "approve",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [
            {"name": "amount", "type": "uint160"},
            {"name": "expiration", "type": "uint48"},
            {"name": "nonce", "type": "uint48"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# UniversalRouter ABI — execute(commands, inputs, deadline)
# Source: https://docs.uniswap.org/contracts/universal-router/technical-reference
UNIVERSAL_ROUTER_ABI = [
    {
        "inputs": [
            {"name": "commands", "type": "bytes"},
            {"name": "inputs", "type": "bytes[]"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "execute",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    }
]

# PoolManager ABI — getSlot0(PoolId) for on-chain token pricing
# Source: https://docs.uniswap.org/contracts/v4/concepts/pool-manager
POOL_MANAGER_ABI = [
    {
        "inputs": [{"name": "id", "type": "bytes32"}],
        "name": "getSlot0",
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "protocolFee", "type": "uint24"},
            {"name": "lpFee", "type": "uint24"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

# Price cache TTL — how often to re-query pool price per token
PRICE_CACHE_TTL = 15


class ChainContext:
    """Holds per-chain Web3 + contracts for executing swaps."""

    def __init__(self, chain_id, w3, account):
        self.chain_id = chain_id
        self.config = CHAINS[chain_id]
        self.w3 = w3
        self.account = account
        self.router = w3.eth.contract(
            address=Web3.to_checksum_address(self.config["universal_router"]),
            abi=UNIVERSAL_ROUTER_ABI,
        )
        self.permit2 = w3.eth.contract(
            address=Web3.to_checksum_address(PERMIT2), abi=PERMIT2_ABI
        )
        self.pool_manager = w3.eth.contract(
            address=Web3.to_checksum_address(self.config["pool_manager"]),
            abi=POOL_MANAGER_ABI,
        )
        self._gas_cache = None
        self._gas_cache_time = 0


class AutonomousTrader:
    def __init__(self):
        self.account = Account.from_key(PRIVATE_KEY)

        # Mainnet pricing connection
        self.w3_mainnet = Web3(Web3.HTTPProvider(MAINNET_RPC))
        if not self.w3_mainnet.is_connected():
            print("Cannot connect to Mainnet RPC")
            sys.exit(1)
        self.mainnet_quoter = self.w3_mainnet.eth.contract(
            address=MAINNET_QUOTER_V2, abi=QUOTER_ABI
        )

        # Shared subsystems
        self.registry = TokenRegistry()
        self.whitelist = WhitelistManager()
        self.event_queue = queue.Queue()

        # Chain connections
        self.chain_ctx = {}
        self._initialize_direct_chains()

        # Per-chain monitors
        self.monitors = {}
        for chain_id, ctx in self.chain_ctx.items():
            mon = TokenMonitor(
                w3=ctx.w3,
                wallet_address=self.account.address,
                chain_id=chain_id,
                registry=self.registry,
            )
            # Watch USDC + WETH on each chain
            cfg = CHAINS[chain_id]
            mon.add_watch(cfg["usdc"])
            mon.add_watch(cfg["weth"])
            self.monitors[chain_id] = mon

        # Trading state — positions keyed by (chain_id, token_addr)
        self.positions = {}  # {"chain_id:token_addr": [pos, ...]}
        self.total_pnl = 0.0
        self.trade_count = 0
        self.take_profit = DEFAULT_TAKE_PROFIT
        self.stop_loss = DEFAULT_STOP_LOSS

        # Active token configs: {"chain_id:addr": {pool_config, ...}}
        self._active_tokens = {}
        self._price_cache = {}  # {(chain_id, addr): (timestamp, price)}

        self._load_state()

        chains_str = ", ".join(CHAINS[c]["name"] for c in self.chain_ctx)
        print(f"\n  Wallet:  {self.account.address}")
        print(f"  Chains:  {chains_str}")

    def _initialize_direct_chains(self):
        """Initialize chain connections from environment RPC URLs."""
        # Load RPC URLs from environment
        rpc_env_map = {
            "TESTNET_RPC_URL": None,
            "MAINNET_RPC_URL": None,
            "BASE_SEPOLIA_RPC_URL": 84532,
            "ARBITRUM_SEPOLIA_RPC_URL": 421614,
            "SEPOLIA_RPC_URL": 11155111,
            "BASE_RPC_URL": 8453,
            "ARBITRUM_RPC_URL": 42161,
            "OPTIMISM_RPC_URL": 10,
            "POLYGON_RPC_URL": 137,
        }

        seen_chain_ids = set()

        for env_key, expected_chain_id in rpc_env_map.items():
            rpc_url = os.getenv(env_key)
            if not rpc_url:
                continue

            try:
                w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
                if not w3.is_connected():
                    print(f"  [Chain Init] {env_key}: Connection failed")
                    continue

                actual_chain_id = w3.eth.chain_id

                # Skip if we already have this chain
                if actual_chain_id in seen_chain_ids:
                    continue

                # Must be in our CHAINS config
                if actual_chain_id not in CHAINS:
                    print(
                        f"  [Chain Init] {env_key}: chain {actual_chain_id} "
                        f"not in CHAINS config, skipping"
                    )
                    continue

                name = CHAINS[actual_chain_id]["name"]
                self.chain_ctx[actual_chain_id] = ChainContext(
                    actual_chain_id, w3, self.account
                )
                seen_chain_ids.add(actual_chain_id)

                print(f"  [Chain Init] Connected: {name} (chain {actual_chain_id})")

            except Exception as e:
                print(f"  [Chain Init] {env_key} error: {e}")
        print("  Pricing: On-chain pool slot0 only")

    # -- State persistence --

    def _load_state(self):
        """Load positions from state file."""
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            self.positions = state.get("positions", {})
            self.total_pnl = state.get("total_pnl", 0.0)
            self.trade_count = state.get("trade_count", 0)
            if self.positions:
                count = sum(len(v) for v in self.positions.values())
                print(
                    f"  Restored {count} positions across {len(self.positions)} tokens"
                )
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_state(self):
        """Persist positions to disk."""
        state = {
            "positions": self.positions,
            "total_pnl": self.total_pnl,
            "trade_count": self.trade_count,
            "updated": datetime.now().isoformat(),
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _save_wallet(self):
        """Update wallet stats for dashboard."""
        # Sum balances across all chains
        total_eth = 0.0
        total_weth = 0.0
        total_usdc = 0.0

        # We need to fetch balances if not recently fetched.
        # Check specific chains (Mainnet + L2s)
        for chain_id in [1, 8453, 42161, 10, 137]:
            if chain_id in self.chain_ctx:
                cfg = CHAINS[chain_id]
                # Native ETH
                try:
                    eth_bal = self.chain_ctx[chain_id].w3.eth.get_balance(
                        self.account.address
                    )
                    total_eth += float(Web3.from_wei(eth_bal, "ether"))
                except Exception:
                    pass

                # WETH
                b, _, _ = self.get_balance(cfg["weth"], chain_id)
                total_weth += b

                # USDC
                b, _, _ = self.get_balance(cfg["usdc"], chain_id)
                total_usdc += b

        eth_price = self.get_mainnet_price()  # get real mainnet price

        data = {
            "eth": total_eth,
            "weth": total_weth,
            "usdc": total_usdc,
            "mainnet_price": eth_price,
            "wallet": self.account.address,
            "execution_network": "Multichain",
            "pricing_source": "Pool (Gecko+OnChain)",
            "updated": datetime.now().isoformat(),
            "chains": [CHAINS[c]["name"] for c in self.chain_ctx],
        }
        try:
            with open(WALLET_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"  Wallet save error: {e}")

        return total_eth, total_weth, total_usdc, eth_price

    # -- Pricing (Mainnet) --

    def get_mainnet_price(
        self, token_in=None, token_out=None, amount=1.0, decimals_in=18
    ):
        """Get price from Mainnet QuoterV2. Defaults to WETH/USDC."""
        try:
            t_in = token_in or MAINNET_WETH
            t_out = token_out or MAINNET_USDC
            amount_in = int(amount * (10**decimals_in))
            result = self.mainnet_quoter.functions.quoteExactInputSingle(
                {
                    "tokenIn": t_in,
                    "tokenOut": t_out,
                    "amountIn": amount_in,
                    "fee": MAINNET_FEE_TIER,
                    "sqrtPriceLimitX96": 0,
                }
            ).call()
            return result[0] / 1e6 / amount
        except Exception as e:
            print(f"  Price error: {e}")
            return None

    # -- Gas helpers --

    def get_gas_params(self, chain_id):
        """Get gas parameters for a specific chain, cached for 10 seconds."""
        ctx = self.chain_ctx[chain_id]
        now = time.time()
        if ctx._gas_cache and now - ctx._gas_cache_time < 10:
            return ctx._gas_cache

        try:
            latest = ctx.w3.eth.get_block("latest")
            base_fee = latest.get("baseFeePerGas", ctx.w3.eth.gas_price)
            max_priority = ctx.w3.to_wei(1, "gwei")
            max_fee = base_fee * 2 + max_priority
            ctx._gas_cache = {
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": max_priority,
            }
        except Exception:
            ctx._gas_cache = {"gasPrice": ctx.w3.eth.gas_price * 2}
        ctx._gas_cache_time = now
        return ctx._gas_cache

    def get_nonce(self, chain_id):
        ctx = self.chain_ctx[chain_id]
        return ctx.w3.eth.get_transaction_count(self.account.address, "pending")

    def gas_cost_usd(self, gas_eth, eth_price):
        return gas_eth * eth_price

    def estimate_swap_gas_usd(self, chain_id, eth_price):
        """Estimate gas cost in USD for a 600k-gas swap on a chain.
        Used to pre-check whether a TP exit would be net-positive."""
        try:
            ctx = self.chain_ctx[chain_id]
            gas_params = self.get_gas_params(chain_id)
            # Use maxFeePerGas if EIP-1559, else gasPrice
            gas_price = gas_params.get("maxFeePerGas", gas_params.get("gasPrice", 0))
            gas_cost_wei = 600000 * gas_price
            gas_cost_eth = float(ctx.w3.from_wei(gas_cost_wei, "ether"))
            return gas_cost_eth * eth_price, gas_cost_eth
        except Exception:
            return 0, 0

    # -- Token balance helpers --

    def get_balance(self, token_addr, chain_id):
        try:
            ctx = self.chain_ctx[chain_id]
            addr = Web3.to_checksum_address(token_addr)
            contract = ctx.w3.eth.contract(address=addr, abi=ERC20_ABI)
            decimals = contract.functions.decimals().call()
            balance = contract.functions.balanceOf(self.account.address).call()
            return balance / (10**decimals), balance, decimals
        except Exception:
            return 0.0, 0, 18

    # -- Token pricing from pool --

    def get_token_price(self, token_addr, chain_id, pool=None, token_decimals=18):
        """Get token price in USD from on-chain pool slot0.
        Returns float USD price per token unit, or None.
        """
        addr = token_addr.lower()
        chain_key = str(chain_id)

        # Check cache
        cache_key = (chain_id, addr)
        now = time.time()
        if cache_key in self._price_cache:
            ts, price = self._price_cache[cache_key]
            if now - ts < PRICE_CACHE_TTL:
                return price

        if pool is None:
            pool = self.registry.get_best_pool(addr, chain_key)
        if not pool:
            return None

        price = self._get_v4_pool_price(addr, chain_id, pool, token_decimals)

        if price is not None and price > 0:
            self._price_cache[cache_key] = (now, price)
            return price

        return None

    def _get_v4_pool_price(self, token_addr, chain_id, pool, token_decimals=18):
        """Read token price from the on-chain pool's slot0.

        Supports both V3 (direct pool contract) and V4 (PoolManager).
        Computes price from sqrtPriceX96.
        Always reads from mainnet — testnet pools are not used for pricing.
        """
        # For testnets, use the corresponding mainnet for pricing
        price_chain_id = TESTNET_TO_MAINNET.get(chain_id, chain_id)
        ctx = self.chain_ctx.get(price_chain_id)
        if not ctx:
            # Fallback: if mainnet chain not in chain_ctx, use w3_mainnet directly
            if price_chain_id == 1:
                w3 = self.w3_mainnet
            else:
                return None
        else:
            w3 = ctx.w3

        dex = (pool.get("dex") or "").lower()
        quote_type = (pool.get("quote_token") or "").upper()
        if quote_type in ("USDC", "USDT"):
            quote_decimals = 6
        else:
            quote_decimals = 18

        # For testnets, map token/quote to mainnet equivalents
        price_token_addr = token_addr
        quote_addr = pool.get("quote_token_address")
        if chain_id in TESTNET_CHAINS:
            mainnet_id = TESTNET_TO_MAINNET[chain_id]
            mainnet_cfg = CHAINS[mainnet_id]
            testnet_cfg = CHAINS[chain_id]
            # Map testnet WETH/USDC to mainnet
            if quote_addr and quote_addr.lower() == testnet_cfg["weth"].lower():
                quote_addr = mainnet_cfg["weth"]
            elif quote_addr and quote_addr.lower() == testnet_cfg["usdc"].lower():
                quote_addr = mainnet_cfg["usdc"]
            # Token itself — if same symbol exists on mainnet with same address, use it
            # (UNI is same address on mainnet and testnets)

        sqrt_price_x96 = None
        token_is_0 = None

        # For V3 pools: find the mainnet pool via Factory, then read slot0
        fee_tier = pool.get("fee_tier", 3000)
        if "v3" in dex and quote_addr:
            try:
                # Find the pool on the pricing chain via V3 Factory
                price_cfg = CHAINS[price_chain_id]
                factory_addr = price_cfg.get("v3_factory")
                if not factory_addr:
                    return None
                factory = w3.eth.contract(
                    address=Web3.to_checksum_address(factory_addr), abi=V3_FACTORY_ABI
                )
                mainnet_pool = factory.functions.getPool(
                    Web3.to_checksum_address(price_token_addr),
                    Web3.to_checksum_address(quote_addr),
                    fee_tier,
                ).call()
                zero = "0x0000000000000000000000000000000000000000"
                if mainnet_pool == zero:
                    return None

                v3_slot0_abi = [
                    {
                        "inputs": [],
                        "name": "slot0",
                        "outputs": [
                            {"name": "sqrtPriceX96", "type": "uint160"},
                            {"name": "tick", "type": "int24"},
                            {"name": "observationIndex", "type": "uint16"},
                            {"name": "observationCardinality", "type": "uint16"},
                            {"name": "observationCardinalityNext", "type": "uint16"},
                            {"name": "feeProtocol", "type": "uint8"},
                            {"name": "unlocked", "type": "bool"},
                        ],
                        "stateMutability": "view",
                        "type": "function",
                    },
                    {
                        "inputs": [],
                        "name": "token0",
                        "outputs": [{"name": "", "type": "address"}],
                        "stateMutability": "view",
                        "type": "function",
                    },
                ]
                pool_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(mainnet_pool), abi=v3_slot0_abi
                )
                slot0 = pool_contract.functions.slot0().call()
                sqrt_price_x96 = slot0[0]
                token0 = pool_contract.functions.token0().call()
                token_is_0 = price_token_addr.lower() == token0.lower()
            except Exception as e:
                print(f"  V3 pool price error: {e}")

        # --- V4: read from PoolManager ---
        elif quote_addr:
            tick_spacing_map = {100: 1, 500: 10, 3000: 60, 10000: 200}
            tick_spacing = tick_spacing_map.get(fee_tier, 60)

            addr_in = Web3.to_checksum_address(price_token_addr)
            addr_quote = Web3.to_checksum_address(quote_addr)

            if int(addr_in, 16) < int(addr_quote, 16):
                currency0, currency1 = addr_in, addr_quote
                token_is_0 = True
            else:
                currency0, currency1 = addr_quote, addr_in
                token_is_0 = False

            hooks = "0x0000000000000000000000000000000000000000"
            pool_key_encoded = encode(
                ["address", "address", "uint24", "int24", "address"],
                [currency0, currency1, fee_tier, tick_spacing, hooks],
            )
            pool_id = Web3.keccak(pool_key_encoded)

            try:
                price_ctx = self.chain_ctx.get(price_chain_id)
                if not price_ctx:
                    return None
                slot0 = price_ctx.pool_manager.functions.getSlot0(pool_id).call()
                sqrt_price_x96 = slot0[0]
            except Exception as e:
                print(f"  V4 pool price error: {e}")

        if sqrt_price_x96 is None or sqrt_price_x96 == 0:
            return None
        if token_is_0 is None:
            return None

        # sqrtPriceX96 → human price
        price_raw = (sqrt_price_x96 / (2**96)) ** 2

        if token_is_0:
            d0, d1 = token_decimals, quote_decimals
        else:
            d0, d1 = quote_decimals, token_decimals

        price_human = price_raw * (10 ** (d0 - d1))

        if token_is_0:
            token_price_in_quote = price_human
        else:
            if price_human <= 0:
                return None
            token_price_in_quote = 1.0 / price_human

        # Convert to USD
        if quote_type in ("USDC", "USDT", "DAI"):
            return token_price_in_quote
        elif quote_type in ("WETH", "ETH"):
            eth_price = self.get_mainnet_price()
            if eth_price:
                return token_price_in_quote * eth_price

        return token_price_in_quote

    # -- On-chain pool discovery via V3 Factory --

    def discover_v3_pool(self, token_addr, chain_id):
        """Find V3 pool on-chain via Factory.getPool().
        Tries WETH and USDC as quote tokens, all fee tiers.
        Returns pool dict or None.
        """
        ctx = self.chain_ctx.get(chain_id)
        if not ctx:
            return None
        cfg = CHAINS[chain_id]
        factory_addr = cfg.get("v3_factory")
        if not factory_addr:
            return None

        factory = ctx.w3.eth.contract(
            address=Web3.to_checksum_address(factory_addr), abi=V3_FACTORY_ABI
        )
        token_cs = Web3.to_checksum_address(token_addr)
        zero = "0x0000000000000000000000000000000000000000"

        # Try WETH then USDC as quote
        quote_options = [
            (cfg["weth"], "WETH", cfg.get("weth_decimals", 18)),
            (cfg["usdc"], "USDC", cfg.get("usdc_decimals", 6)),
        ]

        best = None
        for quote_addr, quote_sym, q_dec in quote_options:
            quote_cs = Web3.to_checksum_address(quote_addr)
            if token_cs.lower() == quote_cs.lower():
                continue
            for fee in V3_FEE_TIERS:
                try:
                    pool_addr = factory.functions.getPool(
                        token_cs, quote_cs, fee
                    ).call()
                    if pool_addr == zero:
                        continue
                    # Pool exists — register it
                    chain_name = cfg["name"]
                    chain_key = str(chain_id)
                    self.registry.add_pool(
                        token_address=token_addr.lower(),
                        pool_address=pool_addr.lower(),
                        chain=chain_key,
                        dex="uniswap_v3",
                        fee_tier=fee,
                        quote_token=quote_sym,
                        quote_token_address=quote_addr.lower(),
                    )
                    print(
                        f"  [V3] Found {quote_sym} pool on "
                        f"{chain_name} fee={fee} "
                        f"({pool_addr[:10]}...)"
                    )
                    if best is None:
                        best = {
                            "pool_address": pool_addr.lower(),
                            "dex": "uniswap_v3",
                            "fee_tier": fee,
                            "quote_token": quote_sym,
                            "quote_token_address": quote_addr.lower(),
                        }
                except Exception:
                    continue
        return best

    # -- Approval: ERC20 → Permit2 → UniversalRouter --

    def ensure_permit2_approval(self, token_addr, chain_id):
        """
        Two-step approval for Uniswap V4:
        1. ERC20.approve(Permit2, max)
        2. Permit2.approve(token, UniversalRouter, max, expiration)

        Source: https://docs.uniswap.org/contracts/v4/quickstart/swap
        """
        ctx = self.chain_ctx[chain_id]
        addr = Web3.to_checksum_address(token_addr)
        router_addr = Web3.to_checksum_address(ctx.config["universal_router"])
        permit2_addr = Web3.to_checksum_address(PERMIT2)
        token = ctx.w3.eth.contract(address=addr, abi=ERC20_ABI)

        # Step 1: ERC20 → Permit2
        erc20_allowance = token.functions.allowance(
            self.account.address, permit2_addr
        ).call()
        if erc20_allowance < 2**128:
            try:
                gas_params = self.get_gas_params(chain_id)
                tx = token.functions.approve(
                    permit2_addr, 2**256 - 1
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "nonce": self.get_nonce(chain_id),
                        "gas": 100000,
                        **gas_params,
                    }
                )
                signed = self.account.sign_transaction(tx)
                tx_hash = ctx.w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = ctx.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                if receipt["status"] != 1:
                    print(f"  ERC20→Permit2 approval failed for {addr}")
                    return False
                print(f"  ERC20→Permit2 approved: {tx_hash.hex()[:16]}...")
            except Exception as e:
                print(f"  ERC20→Permit2 approval error: {e}")
                return False

        # Step 2: Permit2 → UniversalRouter
        p2_allowance = ctx.permit2.functions.allowance(
            self.account.address, addr, router_addr
        ).call()
        p2_amount = p2_allowance[0]
        p2_expiration = p2_allowance[1]
        now_ts = int(time.time())

        if p2_amount < 2**128 or p2_expiration < now_ts + 3600:
            try:
                gas_params = self.get_gas_params(chain_id)
                max_amount = 2**160 - 1
                expiration = now_ts + 30 * 86400
                tx = ctx.permit2.functions.approve(
                    addr, router_addr, max_amount, expiration
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "nonce": self.get_nonce(chain_id),
                        "gas": 100000,
                        **gas_params,
                    }
                )
                signed = self.account.sign_transaction(tx)
                tx_hash = ctx.w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = ctx.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                if receipt["status"] != 1:
                    print(f"  Permit2→Router approval failed for {addr}")
                    return False
                print(f"  Permit2→Router approved: {tx_hash.hex()[:16]}...")
            except Exception as e:
                print(f"  Permit2→Router approval error: {e}")
                return False

        return True

    # -- V4 Swap Encoding --

    def _encode_v4_swap(
        self,
        token_in,
        token_out,
        amount_in,
        min_amount_out,
        fee_tier,
        tick_spacing=None,
        hooks=None,
    ):
        """
        Encode a V4_SWAP command for UniversalRouter.execute().

        Encoding based on official Uniswap V4 docs:
        - Command: V4_SWAP (0x10)
        - Actions: SWAP_EXACT_IN_SINGLE(6) + SETTLE_ALL(12) + TAKE_ALL(15)
        - PoolKey: (currency0, currency1, fee, tickSpacing, hooks)
        - ExactInputSingleParams: (poolKey, zeroForOne, amountIn,
                                   amountOutMinimum, hookData)

        Source: https://docs.uniswap.org/contracts/v4/quickstart/swap
        """
        addr_in = Web3.to_checksum_address(token_in)
        addr_out = Web3.to_checksum_address(token_out)

        # PoolKey requires currency0 < currency1 (sorted by address)
        if int(addr_in, 16) < int(addr_out, 16):
            currency0 = addr_in
            currency1 = addr_out
            zero_for_one = True
        else:
            currency0 = addr_out
            currency1 = addr_in
            zero_for_one = False

        if tick_spacing is None:
            # Default tick spacing by fee tier
            tick_spacing_map = {100: 1, 500: 10, 3000: 60, 10000: 200}
            tick_spacing = tick_spacing_map.get(fee_tier, 60)

        hooks_addr = hooks or "0x0000000000000000000000000000000000000000"

        # Commands: single byte for V4_SWAP
        commands = bytes([V4_SWAP_COMMAND])

        # Actions: packed bytes
        actions = bytes(
            [
                ACTION_SWAP_EXACT_IN_SINGLE,
                ACTION_SETTLE_ALL,
                ACTION_TAKE_ALL,
            ]
        )

        # Encode ExactInputSingleParams
        # Struct: (PoolKey, bool zeroForOne, uint128 amountIn,
        #          uint128 amountOutMinimum, bytes hookData)
        # PoolKey: (address currency0, address currency1, uint24 fee,
        #           int24 tickSpacing, address hooks)
        swap_params = encode(
            [
                "(address,address,uint24,int24,address)",  # PoolKey
                "bool",  # zeroForOne
                "uint128",  # amountIn
                "uint128",  # amountOutMinimum
                "bytes",
            ],  # hookData
            [
                (currency0, currency1, fee_tier, tick_spacing, hooks_addr),
                zero_for_one,
                amount_in,
                min_amount_out,
                b"",  # empty hookData
            ],
        )

        # Settle params: (currency, maxAmount)
        settle_currency = addr_in
        settle_params = encode(["address", "uint128"], [settle_currency, amount_in])

        # Take params: (currency, minAmount)
        take_currency = addr_out
        take_params = encode(["address", "uint128"], [take_currency, min_amount_out])

        # Encode the V4_SWAP input: (bytes actions, bytes[] params)
        params_array = [swap_params, settle_params, take_params]
        v4_input = encode(["bytes", "bytes[]"], [actions, params_array])

        return commands, [v4_input]

    # -- Swap execution --

    def _check_gas_reserve(self, chain_id):
        """Return True if chain has >= GAS_RESERVE_ETH native balance."""
        ctx = self.chain_ctx[chain_id]
        bal_wei = ctx.w3.eth.get_balance(self.account.address)
        bal_eth = float(ctx.w3.from_wei(bal_wei, "ether"))
        if bal_eth < GAS_RESERVE_ETH:
            chain_name = CHAINS[chain_id]["name"]
            print(
                f"  GAS GUARD: {chain_name} has {bal_eth:.6f} ETH "
                f"(< {GAS_RESERVE_ETH} reserve). Refusing swap."
            )
            return False
        return True

    def _execute_swap(
        self, token_in, token_out, amount_in_wei, fee_tier, label, chain_id, min_out=0
    ):
        """Execute a V4 swap via UniversalRouter. Returns (tx_hash, gas_eth)."""
        # Hard gas reserve check — NEVER go below 0.01 ETH
        if not self._check_gas_reserve(chain_id):
            return None, 0

        if not self.ensure_permit2_approval(token_in, chain_id):
            return None, 0

        ctx = self.chain_ctx[chain_id]

        try:
            commands, inputs = self._encode_v4_swap(
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in_wei,
                min_amount_out=min_out,
                fee_tier=fee_tier,
            )

            deadline = int(time.time()) + 300  # 5 min deadline
            gas_params = self.get_gas_params(chain_id)

            tx = ctx.router.functions.execute(
                commands, inputs, deadline
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": self.get_nonce(chain_id),
                    "gas": 600000,
                    "value": 0,
                    **gas_params,
                }
            )

            signed = self.account.sign_transaction(tx)
            tx_hash = ctx.w3.eth.send_raw_transaction(signed.raw_transaction)
            chain_name = CHAINS[chain_id]["name"]
            print(f"  {label} [{chain_name}] tx: {tx_hash.hex()[:16]}...")

            receipt = ctx.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] == 1:
                gas_cost_wei = receipt["gasUsed"] * receipt["effectiveGasPrice"]
                gas_cost_eth = float(ctx.w3.from_wei(gas_cost_wei, "ether"))
                print(
                    f"  {label} confirmed "
                    f"(gas: {receipt['gasUsed']} units, "
                    f"{gas_cost_eth:.6f} ETH)"
                )
                return tx_hash.hex(), gas_cost_eth

            print(f"  {label} reverted on-chain")
            return None, 0

        except Exception as e:
            print(f"  {label} error: {e}")
            return None, 0

    def swap_token_to_usdc(self, token_addr, amount, decimals, fee_tier, chain_id):
        """Sell token for USDC on a specific chain."""
        amount_wei = int(amount * (10**decimals))
        usdc = CHAINS[chain_id]["usdc"]
        return self._execute_swap(
            token_addr, usdc, amount_wei, fee_tier, f"{token_addr[:8]}→USDC", chain_id
        )

    def swap_usdc_to_token(self, token_addr, usdc_amount, fee_tier, chain_id):
        """Buy token with USDC on a specific chain."""
        amount_wei = int(usdc_amount * 1e6)
        usdc = CHAINS[chain_id]["usdc"]
        return self._execute_swap(
            usdc, token_addr, amount_wei, fee_tier, f"USDC→{token_addr[:8]}", chain_id
        )

    # -- Data sync --

    def record_trade(
        self,
        trade_type,
        token_addr,
        price,
        amount,
        profit=0,
        tx_hash=None,
        symbol=None,
        chain_id=None,
        gas_eth=0,
        gas_usd=0,
    ):
        try:
            chain_name = CHAINS[chain_id]["name"] if chain_id else "Unknown"
            payload = {
                "type": trade_type,
                "token": token_addr,
                "symbol": symbol or token_addr[:8],
                "price": price,
                "amount": amount,
                "profit": profit,
                "gas_eth": round(gas_eth, 8),
                "gas_usd": round(gas_usd, 4),
                "tx_hash": tx_hash,
                "chain_id": chain_id,
                "execution_network": chain_name,
                "pricing_source": "mainnet",
                "timestamp": datetime.now().isoformat(),
            }
            requests.post(f"{API_SERVER}/api/trade", json=payload, timeout=5)
        except Exception:
            pass

    def sync_wallet_data(self, eth_price=None):
        """Sync wallet balances for ALL connected chains.
        Also check for new tokens from whitelisted addresses and automatically enter them."""
        try:
            per_chain = {}
            new_tokens_detected = []

            for chain_id, ctx in self.chain_ctx.items():
                cfg = CHAINS[chain_id]
                eth_bal = float(
                    ctx.w3.from_wei(
                        ctx.w3.eth.get_balance(self.account.address), "ether"
                    )
                )
                weth_bal, _, _ = self.get_balance(cfg["weth"], chain_id)
                usdc_bal, _, _ = self.get_balance(cfg["usdc"], chain_id)
                block = ctx.w3.eth.block_number
                per_chain[str(chain_id)] = {
                    "name": cfg["name"],
                    "eth": round(eth_bal, 6),
                    "weth": round(weth_bal, 6),
                    "usdc": round(usdc_bal, 6),
                    "block": block,
                }

                # Check for new tokens from whitelisted addresses using Etherscan API
                new_tokens = self._check_new_tokens_from_whitelist(chain_id, ctx)
                new_tokens_detected.extend(new_tokens)

            # Aggregate totals
            total_eth = sum(c["eth"] for c in per_chain.values())
            total_usdc = sum(c["usdc"] for c in per_chain.values())
            total_weth = sum(c["weth"] for c in per_chain.values())

            wallet_data = {
                "eth": round(total_eth, 6),
                "weth": round(total_weth, 6),
                "usdc": round(total_usdc, 6),
                "wallet": self.account.address,
                "chains": per_chain,
                "execution_network": "Multichain",
                "pricing_source": "Mainnet",
                "mainnet_price": (round(eth_price, 2) if eth_price else None),
                "total_pnl": round(self.total_pnl, 4),
                "positions": {k: len(v) for k, v in self.positions.items() if v},
                "updated": datetime.now().isoformat(),
            }
            with open("/tmp/bot_wallet.json", "w") as f:
                json.dump(wallet_data, f, indent=2)

            # Automatically enter new tokens with trading strategies
            for token_info in new_tokens_detected:
                self._enter_token_with_strategy(token_info)

            return total_eth, total_weth, total_usdc
        except Exception as e:
            print(f"  Wallet sync error: {e}")
            return None, None, None

    # -- Emergency controls --

    def check_stop(self):
        """Check if emergency stop flag is set."""
        return os.path.exists(STOP_FLAG)

    def check_sell_all(self):
        """Check if sell-all flag is set."""
        return os.path.exists(SELL_ALL_FLAG)

    def clear_sell_all(self):
        """Remove sell-all flag after processing."""
        try:
            os.remove(SELL_ALL_FLAG)
        except FileNotFoundError:
            pass

    def sell_all_to_usdc(self, eth_price):
        """Liquidate all positions across all chains to USDC.
        Respects GAS_RESERVE_ETH — skips chains below reserve."""
        print("  EMERGENCY: Selling all positions to USDC")

        for pos_key, pos_list in list(self.positions.items()):
            if not pos_list:
                continue

            # pos_key = "chain_id:token_addr"
            parts = pos_key.split(":", 1)
            if len(parts) != 2:
                continue
            chain_id = int(parts[0])
            token_addr = parts[1]

            if chain_id not in self.chain_ctx:
                print(f"  No context for chain {chain_id}, skipping")
                continue

            chain_config = CHAINS[chain_id]
            usdc_addr = chain_config["usdc"]
            weth_addr = chain_config["weth"]

            pool = self.registry.get_best_pool(token_addr, str(chain_id))
            if not pool:
                print(f"  No pool for {token_addr} on {chain_config['name']}, skipping")
                continue

            human_bal, raw_bal, decimals = self.get_balance(token_addr, chain_id)
            if human_bal < 0.000001:
                continue

            fee_tier = pool.get("fee_tier", 3000)

            total_gas_eth = 0
            if pool.get("quote_token") == "WETH":
                tx, gas = self._execute_swap(
                    token_addr,
                    weth_addr,
                    raw_bal,
                    fee_tier,
                    f"LIQUIDATE {token_addr[:8]}→WETH",
                    chain_id,
                )
                total_gas_eth += gas
                if tx:
                    weth_bal, weth_raw, _ = self.get_balance(weth_addr, chain_id)
                    if weth_raw > 0:
                        _, gas2 = self._execute_swap(
                            weth_addr,
                            usdc_addr,
                            weth_raw,
                            500,
                            "LIQUIDATE WETH→USDC",
                            chain_id,
                        )
                        total_gas_eth += gas2
            else:
                tx, gas = self._execute_swap(
                    token_addr,
                    usdc_addr,
                    raw_bal,
                    fee_tier,
                    f"LIQUIDATE {token_addr[:8]}→USDC",
                    chain_id,
                )
                total_gas_eth += gas

            gas_usd = self.gas_cost_usd(total_gas_eth, eth_price)
            for pos in pos_list:
                entry_price = pos.get("entry_price_usd", pos.get("entry_price", 0))
                gross_pnl = (eth_price - entry_price) * pos["amount"]
                share = total_gas_eth / len(pos_list)
                share_usd = gas_usd / len(pos_list)
                net_pnl = gross_pnl - share_usd
                self.total_pnl += net_pnl
                self.trade_count += 1
                self.record_trade(
                    "SELL",
                    token_addr,
                    eth_price,
                    pos["amount"],
                    net_pnl,
                    tx,
                    symbol=pos.get("symbol"),
                    chain_id=chain_id,
                    gas_eth=share,
                    gas_usd=share_usd,
                )

        self.positions = {}
        self._save_state()
        self.clear_sell_all()
        print("  EMERGENCY: All positions liquidated")

    # -- Token activation --

    def activate_token(self, token_address, chain_id, symbol=None, decimals=18):
        """After pool discovery, activate token for trading."""
        addr = token_address.lower()
        pos_key = f"{chain_id}:{addr}"
        pool = self.registry.get_best_pool(addr, str(chain_id))

        # If no pool or missing quote_token_address, discover
        # on-chain via V3 Factory
        if not pool or not pool.get("quote_token_address"):
            v3_pool = self.discover_v3_pool(addr, chain_id)
            if v3_pool:
                pool = self.registry.get_best_pool(addr, str(chain_id))
            elif not pool:
                return

        self._active_tokens[pos_key] = {
            "symbol": symbol or "???",
            "decimals": decimals,
            "chain_id": chain_id,
            "pool": pool,
        }
        chain_name = CHAINS[chain_id]["name"]
        self.whitelist.set_token_status(addr, chain_id, "active")
        print(
            f"  [Activated] {symbol or '???'} on {chain_name} "
            f"via {pool.get('dex', '?')} "
            f"(fee: {pool.get('fee_tier', '?')})"
        )

        # Persist to tokens/erc20/addresses.json
        self._save_token_address(addr, chain_id, chain_name, symbol or "???")

    TOKEN_ADDRESSES_FILE = Path("/home/sauly/hummingbot/tokens/erc20/addresses.json")
    POOLS_FILE = Path("/home/sauly/hummingbot/tokens/pools/discovered.json")

    def _save_token_address(self, addr, chain_id, chain_name, symbol):
        """Persist activated token and pool to JSON files.
        - tokens/erc20/addresses.json — token contracts
        - tokens/pools/discovered.json — pool contracts
        """
        cid = str(chain_id)

        # Save token to erc20/addresses.json
        try:
            if self.TOKEN_ADDRESSES_FILE.exists():
                data = json.loads(self.TOKEN_ADDRESSES_FILE.read_text())
            else:
                data = {}
            chain_tokens = data.setdefault(cid, {})
            chain_tokens[symbol.lower()] = addr
            self.TOKEN_ADDRESSES_FILE.write_text(json.dumps(data, indent=2) + "\n")
        except Exception as e:
            print(f"  [Warn] Could not save token: {e}")

        # Save pool to pools/discovered.json
        pool = self.registry.get_best_pool(addr, cid)
        if pool:
            try:
                if self.POOLS_FILE.exists():
                    pdata = json.loads(self.POOLS_FILE.read_text())
                else:
                    pdata = {}
                chain_pools = pdata.setdefault(cid, {})
                chain_pools[symbol.lower()] = {
                    "token": addr,
                    "pool": pool.get("pool_address"),
                    "dex": pool.get("dex"),
                    "fee": pool.get("fee_tier"),
                    "quote": pool.get("quote_token"),
                    "quote_address": pool.get("quote_token_address"),
                }
                self.POOLS_FILE.parent.mkdir(parents=True, exist_ok=True)
                self.POOLS_FILE.write_text(json.dumps(pdata, indent=2) + "\n")
            except Exception as e:
                print(f"  [Warn] Could not save pool: {e}")

    # -- Wallet scan for existing tokens --

    def _load_static_addresses(self):
        """Ingest tokens from tokens/erc20/addresses.json into registry."""
        if not self.TOKEN_ADDRESSES_FILE.exists():
            return

        try:
            data = json.loads(self.TOKEN_ADDRESSES_FILE.read_text())
        except Exception:
            return

        contracts = data.get("erc20_contracts", {})

        # Map common keys to chain_id
        key_map = {
            "sepolia": 11155111,
            "ethereum_sepolia": 11155111,
            "arbitrum_sepolia": 421614,
            "base_sepolia": 84532,
            "optimism_sepolia": 11155420,
            # Mainnets
            "ethereum": 1,
            "arbitrum": 42161,
            "base": 8453,
            "optimism": 10,
            "polygon": 137,
        }

        count = 0
        for net_key, tokens in contracts.items():
            chain_id = key_map.get(net_key.lower())
            if not chain_id:
                continue

            for symbol, addr in tokens.items():
                if not addr:
                    continue
                # Add to registry if missing
                try:
                    existing = self.registry.get_token(addr, str(chain_id))
                    if not existing:
                        self.registry.add_token(
                            addr,
                            str(chain_id),
                            symbol=symbol.upper(),
                            name=symbol.upper(),
                        )
                        count += 1
                except Exception:
                    pass

        if count > 0:
            print(f"  [Loader] Imported {count} static tokens into registry")

    def _scan_existing_tokens(self):
        """Scan all chains for tokens with existing balances.
        Uses alchemy_getAssetTransfers to find tokens sent to wallet,
        filters by whitelisted senders, and activates any tokens
        that still have a balance.
        """
        # Load static addresses first so registry has them
        self._load_static_addresses()

        print("  Scanning transfer history for whitelisted sends...")
        senders = self.whitelist.get_all_senders()
        if not senders:
            print("  No whitelisted senders — skipping scan")
            return

        sender_set = {s["address"].lower() for s in senders}
        found = 0

        for chain_id, ctx in self.chain_ctx.items():
            cfg = CHAINS[chain_id]
            chain_name = cfg["name"]
            skip = {cfg["usdc"].lower(), cfg["weth"].lower()}

            try:
                # Alchemy getAssetTransfers: find ERC20 transfers
                # TO our wallet
                resp = ctx.w3.provider.make_request(
                    "alchemy_getAssetTransfers",
                    [
                        {
                            "toAddress": self.account.address,
                            "category": ["erc20"],
                            "order": "desc",
                            "maxCount": "0x64",  # last 100
                            "withMetadata": True,
                        }
                    ],
                )
                transfers = resp.get("result", {}).get("transfers", [])

                for tx in transfers:
                    sender = (tx.get("from") or "").lower()
                    if sender not in sender_set:
                        continue

                    addr = (tx.get("rawContract", {}).get("address") or "").lower()
                    if not addr or addr in skip:
                        continue

                    pos_key = f"{chain_id}:{addr}"
                    if pos_key in self._active_tokens:
                        continue

                    # Check if we still hold a balance
                    human_bal, raw_bal, decimals = self.get_balance(addr, chain_id)
                    if human_bal <= 0:
                        continue

                    # Read symbol
                    try:
                        cs = Web3.to_checksum_address(addr)
                        token_c = ctx.w3.eth.contract(address=cs, abi=ERC20_ABI)
                        symbol = token_c.functions.symbol().call()
                    except Exception:
                        symbol = tx.get("asset") or "???"

                    print(
                        f"  [Scan] {symbol} on {chain_name} "
                        f"from {sender[:10]}... "
                        f"(bal: {human_bal:.6f})"
                    )

                    # Auto-whitelist token
                    self.whitelist.whitelist_token(
                        token_address=addr,
                        chain_id=chain_id,
                        symbol=symbol,
                        sender=sender,
                        auto=True,
                    )

                    # Discover pool on-chain via V3 Factory
                    pool = self.discover_v3_pool(addr, chain_id)
                    if pool:
                        self.activate_token(
                            addr, chain_id, symbol=symbol, decimals=decimals
                        )
                        found += 1
                    else:
                        print(f"  [Scan] No pool for {symbol} on {chain_name}")

            except Exception as e:
                err = str(e)
                if "alchemy" not in err.lower():
                    print(f"  [Scan] {chain_name}: {err[:80]}")

        # Second pass: activate any tokens in registry (from
        # monitor or addresses.json) that have pools and balances
        for chain_id, ctx in self.chain_ctx.items():
            cfg = CHAINS[chain_id]
            chain_name = cfg["name"]
            skip = {cfg["usdc"].lower(), cfg["weth"].lower()}

            db_tokens = self.registry.get_all_tokens(chain=str(chain_id))
            for t in db_tokens:
                addr = t["address"].lower()
                if addr in skip:
                    continue
                pos_key = f"{chain_id}:{addr}"
                if pos_key in self._active_tokens:
                    continue

                human_bal, raw_bal, decimals = self.get_balance(addr, chain_id)
                if human_bal <= 0:
                    continue

                pool = self.registry.get_best_pool(addr, str(chain_id))
                if not pool:
                    pool = self.discover_v3_pool(addr, chain_id)
                if pool:
                    symbol = t.get("symbol", "???")
                    print(
                        f"  [Registry] {symbol} on {chain_name} (bal: {human_bal:.6f})"
                    )
                    self.activate_token(
                        addr, chain_id, symbol=symbol, decimals=t.get("decimals", 18)
                    )
                    found += 1

        if found:
            print(f"  Scan complete: {found} tokens activated")
        else:
            print("  Scan complete: no new tokens found")

    def _check_new_tokens_from_whitelist(self, chain_id, ctx):
        """Check for new tokens from whitelisted addresses using Etherscan API."""
        new_tokens = []
        try:
            # Get Etherscan API key
            etherscan_key = os.getenv("ETHERSCAN_API_KEY")
            if not etherscan_key:
                return new_tokens

            # Map chain ID to Etherscan API URL
            etherscan_urls = {
                1: "https://api.etherscan.io/api",
                5: "https://api-goerli.etherscan.io/api",
                11155111: "https://api-sepolia.etherscan.io/api",
                10: "https://api-optimistic.etherscan.io/api",
                420: "https://api-goerli-optimistic.etherscan.io/api",
                11155420: "https://api-sepolia-optimistic.etherscan.io/api",
                56: "https://api.bscscan.com/api",
                97: "https://api-testnet.bscscan.com/api",
                137: "https://api.polygonscan.com/api",
                80001: "https://api-testnet.polygonscan.com/api",
                42161: "https://api.arbiscan.io/api",
                421613: "https://api-goerli.arbiscan.io/api",
                421614: "https://api-sepolia.arbiscan.io/api",
                8453: "https://api.basescan.org/api",
                84531: "https://api-goerli.basescan.org/api",
                84532: "https://api-sepolia.basescan.org/api",
            }

            chain_url = etherscan_urls.get(chain_id)
            if not chain_url:
                return new_tokens

            # Get whitelisted senders
            senders = self.whitelist.get_all_senders()
            if not senders:
                return new_tokens

            sender_addresses = {s["address"].lower() for s in senders}

            # Query Etherscan API for ERC20 token transfers to our wallet
            params = {
                "module": "account",
                "action": "tokentx",
                "address": self.account.address,
                "sort": "desc",
                "apikey": etherscan_key,
                "page": 1,
                "offset": 100,  # Last 100 transfers
            }

            response = requests.get(chain_url, params=params, timeout=10)
            if response.status_code != 200:
                return new_tokens

            data = response.json()
            if data.get("status") != "1":
                return new_tokens

            transfers = data.get("result", [])

            # Check each transfer
            for tx in transfers:
                from_address = tx.get("from", "").lower()
                to_address = tx.get("to", "").lower()
                token_address = tx.get("contractAddress", "").lower()

                # Only interested in transfers TO our wallet FROM whitelisted addresses
                if (
                    to_address != self.account.address.lower()
                    or from_address not in sender_addresses
                ):
                    continue

                # Check if we already have this token registered
                existing_token = self.registry.get_token(token_address, str(chain_id))
                if existing_token:
                    continue  # Already processed this token

                # Get token metadata
                symbol = tx.get("tokenSymbol", "???")
                name = tx.get("tokenName", "Unknown")
                decimals = int(tx.get("tokenDecimal", 18))
                amount = int(tx.get("value", 0))
                human_amount = amount / (10**decimals)

                # Skip dust
                if human_amount < 0.000001:
                    continue

                # Check current balance to confirm we still hold it
                current_balance, raw_balance, _ = self.get_balance(
                    token_address, chain_id
                )
                if current_balance <= 0:
                    continue

                # Register the token
                self.registry.add_token(
                    address=token_address,
                    chain=str(chain_id),
                    symbol=symbol,
                    name=name,
                    decimals=decimals,
                )

                token_info = {
                    "address": token_address,
                    "symbol": symbol,
                    "name": name,
                    "decimals": decimals,
                    "balance": current_balance,
                    "chain_id": chain_id,
                    "sender": from_address,
                }

                new_tokens.append(token_info)

                print(
                    f"  [NEW TOKEN] {symbol} from whitelisted sender {from_address[:10]}... "
                    f"bal: {current_balance:.6f}"
                )

        except Exception as e:
            print(f"  Etherscan token check error: {e}")

        return new_tokens

    def _calculate_token_volatility(
        self, token_address, chain_id, pool=None, sample_periods=20
    ):
        """Calculate token price volatility over recent periods.
        Returns volatility as a percentage (standard deviation of price changes)."""
        try:
            # Get recent price samples
            prices = []
            for i in range(sample_periods):
                price = self.get_token_price(token_address, chain_id, pool)
                if price is not None:
                    prices.append(price)
                    if i < sample_periods - 1:  # Don't sleep after the last sample
                        time.sleep(0.1)  # Small delay between samples

            if len(prices) < 2:
                return None

            # Calculate percentage changes
            pct_changes = []
            for i in range(1, len(prices)):
                if prices[i - 1] > 0:
                    pct_change = (prices[i] - prices[i - 1]) / prices[i - 1] * 100
                    pct_changes.append(pct_change)

            if not pct_changes:
                return None

            # Calculate standard deviation of percentage changes (volatility)
            import statistics

            volatility = (
                statistics.stdev(pct_changes)
                if len(pct_changes) > 1
                else abs(pct_changes[0])
            )

            return volatility

        except Exception as e:
            print(f"  Volatility calculation error: {e}")
            return None

    def _enter_token_with_strategy(self, token_info):
        """Enter a new token with automatic trading strategy."""
        try:
            token_address = token_info["address"]
            chain_id = token_info["chain_id"]
            symbol = token_info["symbol"]
            decimals = token_info["decimals"]
            balance = token_info["balance"]

            # Discover pool on-chain via V3 Factory
            pool = self.discover_v3_pool(token_address, chain_id)
            if not pool:
                print(
                    f"  [STRATEGY] No pool found for {symbol}, skipping strategy entry"
                )
                return

            # Activate token for trading
            self.activate_token(
                token_address, chain_id, symbol=symbol, decimals=decimals
            )

            # Get current price for entry
            entry_price = self.get_token_price(token_address, chain_id, pool, decimals)
            if entry_price is None:
                print(
                    f"  [STRATEGY] Cannot get price for {symbol}, skipping strategy entry"
                )
                return

            # Calculate volatility-based TP/SL levels
            volatility = self._calculate_token_volatility(token_address, chain_id, pool)

            # Use volatility for dynamic TP/SL, fallback to defaults
            if volatility is not None and volatility > 0:
                # Set TP/SL as multiples of volatility (e.g., 1.5x and 1x volatility)
                take_profit_multiplier = 1.5  # 1.5x volatility above entry
                stop_loss_multiplier = 1.0  # 1x volatility below entry

                # Convert volatility percentage to price amounts
                take_profit_price = entry_price * (
                    1 + (volatility * take_profit_multiplier / 100)
                )
                stop_loss_price = entry_price * (
                    1 - (volatility * stop_loss_multiplier / 100)
                )

                print(
                    f"  [VOLATILITY] {symbol}: {volatility:.2f}% → TP: ${take_profit_price:.4f}, SL: ${stop_loss_price:.4f}"
                )
            else:
                # Fallback to default fixed percentages
                take_profit_price = entry_price * self.take_profit  # Default 2% up
                stop_loss_price = entry_price * self.stop_loss  # Default 2% down
                print(
                    f"  [VOLATILITY] {symbol}: Using defaults → TP: ${take_profit_price:.4f}, SL: ${stop_loss_price:.4f}"
                )

            # Use full balance for the position
            token_amount = balance

            # Store position with TP/SL goals for automatic execution
            pos_key = f"{chain_id}:{token_address}"
            if pos_key not in self.positions:
                self.positions[pos_key] = []

            position = {
                "amount": token_amount,
                "amount_raw": int(token_amount * (10**decimals)),
                "entry_price_usd": entry_price,
                "take_profit_price": take_profit_price,
                "stop_loss_price": stop_loss_price,
                "volatility_percent": volatility,
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "status": "active",  # Ready for price monitoring
            }

            self.positions[pos_key].append(position)

            # Pre-approve tokens for trading to avoid delays during execution
            self.ensure_permit2_approval(token_address, chain_id)

            print(
                f"  [STRATEGY] Entered {symbol} with volatility-based TP/SL strategy "
                f"@ ${entry_price:.4f} (TP: ${take_profit_price:.4f}, SL: ${stop_loss_price:.4f}), "
                f"amount: {token_amount:.6f}"
            )

        except Exception as e:
            print(f"  Strategy entry error for {token_info.get('symbol', '???')}: {e}")

    # -- Main loop --

    async def run(self):
        # Initial wallet fetch (saves to WALLET_FILE for dashboard)
        eth_bal, weth_bal, usdc_bal, eth_price = self._save_wallet()

        chains_str = ", ".join(CHAINS[c]["name"] for c in self.chain_ctx)
        pos_count = sum(len(v) for v in self.positions.values())

        print(f"""
========================================================
  AUTONOMOUS TRADER | Uniswap V4 | Multichain
========================================================
  Chains  : {chains_str}
  TP / SL : {(self.take_profit - 1) * 100:.1f}% / {(1 - self.stop_loss) * 100:.1f}%
  Router  : UniversalRouter V4
  Wallet  : {self.account.address}
  Gas Min : {GAS_RESERVE_ETH} ETH per chain
--------------------------------------------------------
  ETH  : {eth_bal:.6f} (all chains)
  WETH : {weth_bal:.6f}
  USDC : {usdc_bal:.6f}
  Price: ${eth_price:.2f} (Mainnet)
  Open : {pos_count} positions
--------------------------------------------------------
  API Server : {API_SERVER}
  Stop flag  : {STOP_FLAG}
  Sell flag  : {SELL_ALL_FLAG}
========================================================
""")

        # Scan wallet for existing tokens across all chains
        self._scan_existing_tokens()

        # Per-chain block tracking
        last_blocks = {}
        for cid, ctx in self.chain_ctx.items():
            try:
                last_blocks[cid] = ctx.w3.eth.block_number
            except Exception:
                last_blocks[cid] = 0

        blocks_since_signal = 0
        last_status_time = 0

        print("Starting multichain trading loop...")

        while True:
            try:
                # Emergency stop check
                if self.check_stop():
                    print("EMERGENCY STOP — flag detected, exiting")
                    self._save_state()
                    break

                # Sell all check
                if self.check_sell_all():
                    eth_price = self.get_mainnet_price() or eth_price
                    self.sell_all_to_usdc(eth_price)

                # Status log every 15 seconds
                now = time.time()
                if now - last_status_time >= 15:
                    last_status_time = now
                    pos_count = sum(len(v) for v in self.positions.values())
                    active = len(self._active_tokens)
                    blocks_str = " | ".join(
                        f"{CHAINS[c]['name'][:3]}:{last_blocks.get(c, 0)}"
                        for c in self.chain_ctx
                    )
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"${eth_price:.2f} | "
                        f"Tokens: {active} | "
                        f"Pos: {pos_count} | "
                        f"PnL: ${self.total_pnl:.4f} | "
                        f"{blocks_str}"
                    )

                # -- Check TP/SL exits for all positions --
                # Token prices come from the pool ONLY, not ETH
                closed_tokens = []
                for pos_key, pos_list in list(self.positions.items()):
                    if not pos_list:
                        closed_tokens.append(pos_key)
                        continue

                    parts = pos_key.split(":", 1)
                    if len(parts) != 2:
                        continue
                    pos_chain_id = int(parts[0])
                    token_addr = parts[1]

                    if pos_chain_id not in self.chain_ctx:
                        continue

                    # Get active token config for pool info
                    config = self._active_tokens.get(pos_key)
                    if not config:
                        continue

                    pool = config["pool"]
                    decimals = config["decimals"]
                    fee_tier = pool.get("fee_tier", 3000)

                    # Get CURRENT token price from pool
                    current_price = self.get_token_price(
                        token_addr, pos_chain_id, pool, token_decimals=decimals
                    )
                    if current_price is None:
                        continue  # Can't price, skip check

                    pos_chain_config = CHAINS[pos_chain_id]
                    closed_indices = []

                    for i, pos in enumerate(pos_list):
                        entry_price = pos.get("entry_price_usd", 0)
                        if entry_price <= 0:
                            continue

                        # Check price-based TP/SL (new approach)
                        take_profit_price = pos.get("take_profit_price")
                        stop_loss_price = pos.get("stop_loss_price")

                        is_tp = is_sl = False
                        change = current_price / entry_price if entry_price > 0 else 1.0

                        if (
                            take_profit_price is not None
                            and stop_loss_price is not None
                        ):
                            # Use price-based TP/SL
                            is_tp = current_price >= take_profit_price
                            is_sl = current_price <= stop_loss_price
                        else:
                            # Fallback to ratio-based TP/SL (original approach)
                            is_tp = change >= self.take_profit
                            is_sl = change <= self.stop_loss

                        if not (is_tp or is_sl):
                            continue

                        gross_pnl = (current_price - entry_price) * pos["amount"]

                        # Gas pre-check (use ETH price for gas
                        # estimation only) — skip on testnets
                        if pos_chain_id not in TESTNET_CHAINS:
                            est_exit_usd, est_exit_eth = self.estimate_swap_gas_usd(
                                pos_chain_id, eth_price or 2000
                            )
                            if is_tp and gross_pnl <= est_exit_usd:
                                symbol = pos.get("symbol", token_addr[:8])
                                print(
                                    f"  SKIP TP {symbol}: "
                                    f"gross ${gross_pnl:.4f} "
                                    f"<= gas ${est_exit_usd:.4f}"
                                )
                                continue

                        # SL always executes to limit loss
                        tag = "TP" if is_tp else "SL"

                        # Execute sell: token → quote token
                        human_bal, raw_bal, _ = self.get_balance(
                            token_addr, pos_chain_id
                        )
                        tx, gas_eth = None, 0

                        if raw_bal > 0:
                            sell_amount = min(
                                raw_bal, int(pos["amount"] * (10**decimals))
                            )

                            # Sell to USDC (direct or via WETH)
                            quote_type = (pool.get("quote_token") or "").upper()
                            if quote_type == "WETH":
                                weth = pos_chain_config["weth"]
                                tx, gas_eth = self._execute_swap(
                                    token_addr,
                                    weth,
                                    sell_amount,
                                    fee_tier,
                                    f"{tag} {pos.get('symbol', '?')}→WETH",
                                    pos_chain_id,
                                )
                                if tx:
                                    wb, wr, _ = self.get_balance(weth, pos_chain_id)
                                    if wr > 0:
                                        _, g2 = self._execute_swap(
                                            weth,
                                            pos_chain_config["usdc"],
                                            wr,
                                            500,
                                            "WETH→USDC",
                                            pos_chain_id,
                                        )
                                        gas_eth += g2
                            else:
                                usdc = pos_chain_config["usdc"]
                                tx, gas_eth = self._execute_swap(
                                    token_addr,
                                    usdc,
                                    sell_amount,
                                    fee_tier,
                                    f"{tag} {pos.get('symbol', '?')}→USDC",
                                    pos_chain_id,
                                )

                        gas_usd = self.gas_cost_usd(gas_eth, eth_price or 2000)
                        net_pnl = gross_pnl - gas_usd

                        symbol = pos.get("symbol", token_addr[:8])
                        chain_name = pos_chain_config["name"]
                        pct = (change - 1) * 100
                        print(
                            f"  {tag} {symbol} [{chain_name}] "
                            f"${current_price:.6f} "
                            f"(entry ${entry_price:.6f}, "
                            f"{pct:+.2f}%, "
                            f"gas ${gas_usd:.4f}, "
                            f"net ${net_pnl:.4f})"
                        )

                        self.total_pnl += net_pnl
                        self.trade_count += 1
                        self.record_trade(
                            "SELL",
                            token_addr,
                            current_price,
                            pos["amount"],
                            net_pnl,
                            tx,
                            symbol=symbol,
                            chain_id=pos_chain_id,
                            gas_eth=gas_eth,
                            gas_usd=gas_usd,
                        )
                        closed_indices.append(i)

                    for i in reversed(closed_indices):
                        pos_list.pop(i)

                # Clean empty position lists
                for t in closed_tokens:
                    if not self.positions.get(t):
                        self.positions.pop(t, None)

                # -- Check entries for active tokens --
                # Entry = HOLD the token, record position with
                # pool price. No swap on entry.
                blocks_since_signal += 1
                if blocks_since_signal >= DEFAULT_SIGNAL_INTERVAL:
                    blocks_since_signal = 0
                    for pos_key, config in self._active_tokens.items():
                        pool = config["pool"]
                        symbol = config["symbol"]
                        decimals = config["decimals"]
                        entry_chain_id = config.get("chain_id")

                        if not entry_chain_id or entry_chain_id not in self.chain_ctx:
                            continue

                        # pos_key is "chain_id:token_addr"
                        token_addr = pos_key.split(":", 1)[1]

                        human_bal, raw_bal, _ = self.get_balance(
                            token_addr, entry_chain_id
                        )
                        if human_bal <= 0:
                            continue
                        if self.positions.get(pos_key, []):
                            continue

                        # Get token price from pool
                        token_price = self.get_token_price(
                            token_addr, entry_chain_id, pool, token_decimals=decimals
                        )
                        if token_price is None or token_price <= 0:
                            print(f"  Cannot price {symbol} from pool, skipping entry")
                            continue

                        # Gas profitability pre-check
                        # (exit gas must be < TP profit)
                        # Skip check on testnets — no real value
                        pos_value = human_bal * token_price
                        if entry_chain_id not in TESTNET_CHAINS:
                            est_gas_usd, _ = self.estimate_swap_gas_usd(
                                entry_chain_id, eth_price or 2000
                            )
                            expected_tp = pos_value * (self.take_profit - 1)
                            if est_gas_usd >= expected_tp:
                                print(
                                    f"  SKIP ENTRY {symbol}: "
                                    f"exit gas ${est_gas_usd:.4f} "
                                    f">= TP profit "
                                    f"${expected_tp:.4f}"
                                )
                                continue

                        # HOLD: record position, no swap
                        pos = {
                            "entry_price_usd": token_price,
                            "amount": human_bal,
                            "decimals": decimals,
                            "value_usd": pos_value,
                            "symbol": symbol,
                            "token": token_addr,
                            "chain_id": entry_chain_id,
                            "fee_tier": pool.get("fee_tier", 3000),
                            "timestamp": datetime.now().isoformat(),
                        }

                        self.positions.setdefault(pos_key, []).append(pos)
                        self.trade_count += 1

                        chain_name = CHAINS[entry_chain_id]["name"]
                        print(
                            f"  HOLD {symbol} [{chain_name}]: "
                            f"{human_bal:.6f} @ "
                            f"${token_price:.6f}/unit "
                            f"(${pos_value:.4f} total)"
                        )

                        self.record_trade(
                            "BUY",
                            token_addr,
                            token_price,
                            human_bal,
                            0,
                            None,
                            symbol=symbol,
                            chain_id=entry_chain_id,
                        )

                # Save state periodically
                self._save_state()

                await asyncio.sleep(1)

            except KeyboardInterrupt:
                print("\nKeyboard interrupt received")
                self._save_state()
                pass


async def main():
    trader = AutonomousTrader()
    await trader.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
