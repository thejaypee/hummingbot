#!/usr/bin/env python3
"""
TRADING CONFIG — Multi-chain configuration for Uniswap V4 trading.
All contract addresses sourced from official Uniswap V4 deployment docs:
https://docs.uniswap.org/contracts/v4/deployments
"""

# Permit2 is the same address on all chains
PERMIT2 = "0x000000000022D473030F116dDEE9F6B43aC78BA3"

# Uniswap V3 Factory addresses
# Source: https://docs.uniswap.org/contracts/v3/reference/deployments/
V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"  # Mainnets
V3_FACTORY_SEPOLIA = "0x0227628f3F023bb0B980b67D528571c95c6DaC1c"

# Uniswap V4 UniversalRouter command/action bytes
# Source: docs.uniswap.org/contracts/universal-router/technical-reference
# Source: docs.uniswap.org/sdk/v4/reference/enumerations/Actions
V4_SWAP_COMMAND = 0x10
ACTION_SWAP_EXACT_IN_SINGLE = 6
ACTION_SETTLE_ALL = 12
ACTION_TAKE_ALL = 15

CHAINS = {
    1: {
        "name": "Ethereum",
        "geckoterminal": "eth",
        "pool_manager": "0x000000000004444c5dc75cB358380D2e3dE08A90",
        "universal_router": "0x66a9893cc07d91d95644aedd05d03f95e1dba8af",
        "position_manager": "0xbd216513d74c8cf14cf4747e6aaa6420ff64ee9e",
        "v3_factory": V3_FACTORY,
        "permit2": PERMIT2,
        "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "weth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "quoter_v2": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
    8453: {
        "name": "Base",
        "geckoterminal": "base",
        "pool_manager": "0x498581ff718922c3f8e6a244956af099b2652b2b",
        "universal_router": "0x6ff5693b99212da76ad316178a184ab56d299b43",
        "position_manager": "0x7c5f5a4bbd8fd63184577525326123b519429bdc",
        "v3_factory": V3_FACTORY,
        "permit2": PERMIT2,
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "weth": "0x4200000000000000000000000000000000000006",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
    42161: {
        "name": "Arbitrum",
        "geckoterminal": "arbitrum",
        "pool_manager": "0x360e68faccca8ca495c1b759fd9eee466db9fb32",
        "universal_router": "0xa51afafe0263b40edaef0df8781ea9aa03e381a3",
        "position_manager": "0xd88f38f930b7952f2db2432cb002e7abbf3dd869",
        "v3_factory": V3_FACTORY,
        "permit2": PERMIT2,
        "usdc": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "weth": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
    137: {
        "name": "Polygon",
        "geckoterminal": "polygon_pos",
        "pool_manager": "0x67366782805870060151383f4bbff9dab53e5cd6",
        "universal_router": "0x1095692a6237d83c6a72f3f5efedb9a670c49223",
        "position_manager": "0x1ec2ebf4f37e7363fdfe3551602425af0b3ceef9",
        "v3_factory": V3_FACTORY,
        "permit2": PERMIT2,
        "usdc": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "weth": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
    10: {
        "name": "Optimism",
        "geckoterminal": "optimism",
        "pool_manager": "0x9a13f98cb987694c9f086b1f5eb990eea8264ec3",
        "universal_router": "0x851116d9223fabed8e56c0e6b8ad0c31d98b3507",
        "position_manager": "0x3c3ea4b57a46241e54610e5f022e5c45859a1017",
        "v3_factory": V3_FACTORY,
        "permit2": PERMIT2,
        "usdc": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        "weth": "0x4200000000000000000000000000000000000006",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
    84532: {
        "name": "Base Sepolia",
        "geckoterminal": "base",
        "pool_manager": "0x05E73354cFDd6745C338b50BcFDfA3Aa6fA03408",
        "universal_router": "0x492e6456d9528771018deb9e87ef7750ef184104",
        "position_manager": "0x4b2c77d209d3405f41a037ec6c77f7f5b8e2ca80",
        "v3_factory": V3_FACTORY_SEPOLIA,
        "permit2": PERMIT2,
        "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "weth": "0x4200000000000000000000000000000000000006",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
    421614: {
        "name": "Arbitrum Sepolia",
        "geckoterminal": "arbitrum",
        "pool_manager": "0xFB3e0C6F74eB1a21CC1Da29aeC80D2Dfe6C9a317",
        "universal_router": "0xefd1d4bd4cf1e86da286bb4cb1b8bced9c10ba47",
        "position_manager": "0xAc631556d3d4019C95769033B5E719dD77124BAc",
        "quoter": "0x7de51022d70a725b508085468052e25e22b5c4c9",
        "v3_factory": V3_FACTORY_SEPOLIA,
        "permit2": PERMIT2,
        "usdc": "0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d",
        "weth": "0x980B62Da83eFf3D4576C647993b0c1D7faf17c73",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
    11155111: {
        "name": "Ethereum Sepolia",
        "geckoterminal": "eth",
        "pool_manager": "0xE03A1074c86CFeDd5C142C4F04F1a1536e203543",
        "universal_router": "0x3a9d48ab9751398bbfa63ad67599bb04e4bdf98b",
        "position_manager": "0x429ba70129df741B2Ca2a85BC3A2a3328e5c09b4",
        "v3_factory": V3_FACTORY_SEPOLIA,
        "permit2": PERMIT2,
        "usdc": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
        "weth": "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
        "usdc_decimals": 6,
        "weth_decimals": 18,
    },
}

# Gas reserve — NEVER let native ETH drop below this on any chain
GAS_RESERVE_ETH = 0.01  # 0.01 ETH minimum retained for gas

# Trading defaults
DEFAULT_POSITION_SIZE_ETH = 0.01   # WETH per trade
DEFAULT_TAKE_PROFIT = 1.02         # 2%
DEFAULT_STOP_LOSS = 0.98           # 2%
DEFAULT_SIGNAL_INTERVAL = 10       # blocks between entry checks
DEFAULT_SCAN_INTERVAL = 10         # blocks between token scans

# Emergency control flag files
STOP_FLAG = "/tmp/trader_stop"
SELL_ALL_FLAG = "/tmp/trader_sell_all"
STATE_FILE = "/tmp/multi_positions.json"
WALLET_FILE = "/tmp/bot_wallet.json"
TRADES_FILE = "/tmp/bot_trades.json"


def get_chain_config(chain_id):
    """Get config for a specific chain, raises if not supported."""
    if chain_id not in CHAINS:
        raise ValueError(f"Unsupported chain_id: {chain_id}. "
                         f"Supported: {list(CHAINS.keys())}")
    return CHAINS[chain_id]
