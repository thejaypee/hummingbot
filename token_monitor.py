#!/usr/bin/env python3
"""
TOKEN MONITOR — Detects new ERC20 token arrivals in wallet.
Polls balanceOf() for tracked addresses, compares against TokenRegistry.
New tokens trigger the LiquidityScout pipeline.
"""

from web3 import Web3

from token_registry import TokenRegistry

ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
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
]

# Minimum USD value to bother tracking (skip dust)
MIN_VALUE_USD = 1.0


class TokenMonitor:
    def __init__(self, w3, wallet_address, chain_id, registry=None,
                 watch_list=None):
        """
        Args:
            w3: Web3 instance connected to the execution chain
            wallet_address: Address to monitor for token arrivals
            chain_id: Chain ID (used as registry key)
            registry: TokenRegistry instance (shared)
            watch_list: Optional list of token addresses to actively poll
        """
        self.w3 = w3
        self.wallet = Web3.to_checksum_address(wallet_address)
        self.chain_id = chain_id
        self.chain_key = str(chain_id)
        self.registry = registry or TokenRegistry()
        self.watch_list = set()
        if watch_list:
            for addr in watch_list:
                self.watch_list.add(Web3.to_checksum_address(addr))

        # Track known balances: {address: balance_raw}
        self._known_balances = {}

    def add_watch(self, token_address):
        """Add a token address to the watch list."""
        self.watch_list.add(Web3.to_checksum_address(token_address))

    def remove_watch(self, token_address):
        """Remove a token address from the watch list."""
        self.watch_list.discard(Web3.to_checksum_address(token_address))

    def scan(self):
        """
        Scan all watched tokens for new arrivals or balance changes.
        Returns list of newly detected tokens with metadata:
        [{"address", "symbol", "name", "decimals", "balance", "is_new"}]
        """
        new_tokens = []

        # Also check tokens already in registry for this chain
        db_tokens = self.registry.get_all_tokens(chain=self.chain_key)
        all_addresses = set(self.watch_list)
        for t in db_tokens:
            all_addresses.add(Web3.to_checksum_address(t['address']))

        for token_addr in all_addresses:
            try:
                contract = self.w3.eth.contract(
                    address=token_addr, abi=ERC20_ABI)
                balance = contract.functions.balanceOf(self.wallet).call()

                prev_balance = self._known_balances.get(
                    token_addr.lower(), 0)
                self._known_balances[token_addr.lower()] = balance

                if balance == 0:
                    continue

                # Check if this is a new token (not in registry)
                existing = self.registry.get_token(
                    token_addr, self.chain_key)
                is_new = existing is None

                # New token or balance increased
                if is_new or (balance > prev_balance and prev_balance == 0):
                    metadata = self._read_token_metadata(contract)
                    decimals = metadata.get("decimals", 18)
                    human_balance = balance / (10 ** decimals)

                    # Register in DB
                    self.registry.add_token(
                        address=token_addr,
                        chain=self.chain_key,
                        symbol=metadata.get("symbol"),
                        name=metadata.get("name"),
                        decimals=decimals,
                    )

                    new_tokens.append({
                        "address": token_addr,
                        "symbol": metadata.get("symbol", "???"),
                        "name": metadata.get("name", "Unknown"),
                        "decimals": decimals,
                        "balance_raw": balance,
                        "balance": human_balance,
                        "is_new": is_new,
                    })

                    action = "NEW" if is_new else "DEPOSIT"
                    print(
                        f"  [Monitor] {action}: "
                        f"{metadata.get('symbol', '???')} "
                        f"({token_addr[:10]}...) "
                        f"balance: {human_balance:.6f}")

            except Exception:
                # Token might not be ERC20-compliant, skip silently
                continue

        return new_tokens

    def get_balance(self, token_address):
        """Get current balance of a specific token."""
        try:
            addr = Web3.to_checksum_address(token_address)
            contract = self.w3.eth.contract(address=addr, abi=ERC20_ABI)
            decimals = contract.functions.decimals().call()
            balance = contract.functions.balanceOf(self.wallet).call()
            return balance / (10 ** decimals), balance, decimals
        except Exception:
            return 0.0, 0, 18

    def get_all_balances(self):
        """Get balances of all tracked tokens."""
        balances = {}
        db_tokens = self.registry.get_all_tokens(chain=self.chain_key)
        for t in db_tokens:
            addr = Web3.to_checksum_address(t['address'])
            human, raw, decimals = self.get_balance(addr)
            if human > 0:
                balances[addr.lower()] = {
                    "symbol": t.get("symbol", "???"),
                    "balance": human,
                    "balance_raw": raw,
                    "decimals": decimals,
                }
        return balances

    def _read_token_metadata(self, contract):
        """Read symbol, name, decimals from an ERC20 contract."""
        metadata = {}
        try:
            metadata["symbol"] = contract.functions.symbol().call()
        except Exception:
            metadata["symbol"] = "???"
        try:
            metadata["name"] = contract.functions.name().call()
        except Exception:
            metadata["name"] = "Unknown"
        try:
            metadata["decimals"] = contract.functions.decimals().call()
        except Exception:
            metadata["decimals"] = 18
        return metadata
