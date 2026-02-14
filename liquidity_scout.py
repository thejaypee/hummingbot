#!/usr/bin/env python3
"""
LIQUIDITY SCOUT — Discovers best trading pools for any ERC20 token.

Primary:  GeckoTerminal API (free, deterministic, no key needed)
Backup:   Gemini AI scout (richer analysis when GEMINI_API_KEY is set)
          Source: https://github.com/thejaypee/liquidityScout

Caches results to avoid rate limits (5 min TTL).
"""

import re
import time

import requests

try:
    import gemini_scout
    _GEMINI_AVAILABLE = gemini_scout.is_available()
except ImportError:
    _GEMINI_AVAILABLE = False

from config.trading_config import CHAINS
from token_registry import TokenRegistry

# GeckoTerminal network IDs mapped from chain_id
NETWORK_MAP = {
    1: "eth",
    8453: "base",
    42161: "arbitrum",
    137: "polygon_pos",
    10: "optimism",
    100: "xdai",       # Gnosis
    324: "zksync",
    534352: "scroll",
    84532: "base",          # Base Sepolia (maps to mainnet, no testnet pools)
    421614: "arbitrum",     # Arbitrum Sepolia (maps to mainnet, no testnet pools)
    11155111: "eth",        # Ethereum Sepolia (maps to mainnet, no testnet pools)
}

# Known stablecoin symbols (case-insensitive match)
STABLECOINS = {"usdc", "usdt", "dai", "busd"}
WETH_SYMBOLS = {"weth", "eth"}

# Minimum liquidity to consider a pool viable
MIN_LIQUIDITY_USD = 10_000

# Cache TTL in seconds
CACHE_TTL = 300  # 5 minutes

# GeckoTerminal API base
GECKO_API = "https://api.geckoterminal.com/api/v2"


class LiquidityScout:
    def __init__(self, registry=None):
        self.registry = registry or TokenRegistry()
        self._cache = {}  # {(token, chain): (timestamp, result)}
        self._gemini_cache = {}  # {(token, chain): (timestamp, result)}
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "HummingbotTrader/1.0"
        })
        if _GEMINI_AVAILABLE:
            print("  [Scout] Gemini AI enrichment enabled (backup)")
        else:
            print("  [Scout] GeckoTerminal only "
                  "(set GEMINI_API_KEY for AI enrichment)")

    def find_best_pool(self, token_address, chain_id):
        """
        Find the best trading pool for a token.
        Returns pool config dict or None if no viable pool found.

        Priority: USDC pair > WETH pair > other stablecoin pair
        """
        token_address = token_address.lower()
        chain_key = str(chain_id)

        # Check in-memory cache first
        cache_key = (token_address, chain_key)
        if cache_key in self._cache:
            ts, result = self._cache[cache_key]
            if time.time() - ts < CACHE_TTL:
                return result

        # Check DB cache
        db_pool = self.registry.get_best_pool(token_address, chain_key)
        if db_pool:
            self._cache[cache_key] = (time.time(), db_pool)
            return db_pool

        # Hit GeckoTerminal API
        network = NETWORK_MAP.get(chain_id)
        if not network:
            print(f"  [Scout] Unsupported chain_id: {chain_id}")
            return None

        pool = self._fetch_pools(token_address, network, chain_key)
        self._cache[cache_key] = (time.time(), pool)
        return pool

    def _fetch_pools(self, token_address, network, chain_key):
        """Fetch pools from GeckoTerminal and pick the best one."""
        # Map testnet tokens to mainnet addresses for pricing
        query_address = token_address
        try:
            cid = int(chain_key)
            # If we are on a testnet (based on network mapping)
            if cid in {84532, 421614, 11155111}:
                cfg = CHAINS.get(cid)
                if cfg:
                    # Check if it's a known token
                    if token_address.lower() == cfg.get('usdc', '').lower():
                        # Use corresponding mainnet USDC
                        mainnet_id = {84532: 8453, 421614: 42161, 11155111: 1}.get(cid)
                        if mainnet_id:
                            query_address = CHAINS[mainnet_id]['usdc']
                            print(f"  [Scout] Mapping Testnet USDC to Mainnet {query_address[:10]}...")
                    elif token_address.lower() == cfg.get('weth', '').lower():
                        # Use corresponding mainnet WETH
                        mainnet_id = {84532: 8453, 421614: 42161, 11155111: 1}.get(cid)
                        if mainnet_id:
                            query_address = CHAINS[mainnet_id]['weth']
                            print(f"  [Scout] Mapping Testnet WETH to Mainnet {query_address[:10]}...")
        except Exception as e:
            print(f"  [Scout] mapping error: {e}")

        url = (f"{GECKO_API}/networks/{network}/tokens/"
               f"{query_address}/pools")
        params = {"page": 1}

        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                print("  [Scout] Rate limited, waiting 60s...")
                time.sleep(60)
                resp = self.session.get(url, params=params, timeout=10)

            if resp.status_code != 200:
                print(f"  [Scout] API error {resp.status_code} for "
                      f"{token_address}")
                return None

            data = resp.json()
        except Exception as e:
            print(f"  [Scout] Request error: {e}")
            return None

        pools = data.get("data", [])
        if not pools:
            print(f"  [Scout] No pools found for {token_address}")
            return None

        # Score and rank pools
        candidates = []
        for p in pools:
            attrs = p.get("attributes", {})
            pool_addr = attrs.get("address", "")
            pool_name = attrs.get("name", "")
            reserve_usd = float(attrs.get("reserve_in_usd") or 0)
            volume_24h = float(
                attrs.get("volume_usd", {}).get("h24", 0) or 0)

            if reserve_usd < MIN_LIQUIDITY_USD:
                continue

            # Determine quote token from pool name
            quote_token, quote_type = self._parse_quote_token(
                pool_name, token_address)
            fee_tier = self._parse_fee_tier(pool_name)
            dex = self._parse_dex(p)

            # Score: USDC > WETH > other stable, weighted by liquidity
            if quote_type == "usdc":
                score = 3 * reserve_usd
            elif quote_type == "weth":
                score = 2 * reserve_usd
            elif quote_type == "stable":
                score = 1.5 * reserve_usd
            else:
                score = reserve_usd

            candidates.append({
                "pool_address": pool_addr,
                "dex": dex,
                "fee_tier": fee_tier,
                "quote_token": quote_token,
                "quote_type": quote_type,
                "liquidity_usd": reserve_usd,
                "volume_24h": volume_24h,
                "score": score,
                "raw": p,
            })

        if not candidates:
            print(f"  [Scout] No pools meet ${MIN_LIQUIDITY_USD} "
                  f"liquidity minimum for {token_address}")
            return None

        # Pick highest-scored pool
        best = max(candidates, key=lambda c: c["score"])

        # Extract quote token address from relationships
        quote_addr = self._extract_quote_address(best["raw"],
                                                 token_address)

        # Store in DB
        self.registry.add_pool(
            token_address=token_address,
            pool_address=best["pool_address"],
            chain=chain_key,
            dex=best["dex"],
            fee_tier=best["fee_tier"],
            quote_token=best["quote_token"],
            quote_token_address=quote_addr,
            liquidity_usd=best["liquidity_usd"],
            volume_24h=best["volume_24h"],
        )

        pool_data = self.registry.get_best_pool(token_address, chain_key)
        print(f"  [Scout] Found pool: {best['quote_token']} pair on "
              f"{best['dex']} (${best['liquidity_usd']:,.0f} liq, "
              f"fee {best['fee_tier']})")
        return pool_data

    def _parse_quote_token(self, pool_name, token_address):
        """Parse pool name like 'WETH / USDC 0.05%' to get quote token."""
        parts = re.split(r'\s*/\s*', pool_name.split('%')[0].strip())
        if len(parts) < 2:
            return pool_name, "unknown"

        # The quote is the token that ISN'T our token
        # Pool name usually has both symbols
        for part in parts:
            symbol = part.strip().split()[0].upper()
            if symbol.lower() in STABLECOINS:
                if symbol.upper() == "USDC":
                    return "USDC", "usdc"
                return symbol.upper(), "stable"
            if symbol.lower() in WETH_SYMBOLS:
                return "WETH", "weth"

        return parts[-1].strip().split()[0], "other"

    def _parse_fee_tier(self, pool_name):
        """Extract fee tier from pool name like 'WETH / USDC 0.05%'."""
        match = re.search(r'(\d+\.?\d*)\s*%', pool_name)
        if match:
            pct = float(match.group(1))
            return int(pct * 10000)  # 0.05% -> 500, 0.3% -> 3000
        return 3000  # Default to 0.3%

    def _parse_dex(self, pool_data):
        """Extract DEX name from pool relationships."""
        rels = pool_data.get("relationships", {})
        dex_data = rels.get("dex", {}).get("data", {})
        return dex_data.get("id", "unknown")

    def _extract_quote_address(self, pool_data, token_address):
        """Extract the quote token's contract address."""
        rels = pool_data.get("relationships", {})
        tokens = rels.get("tokens", {}).get("data", [])
        for t in tokens:
            # Token ID format: "network_address"
            parts = t.get("id", "").split("_", 1)
            if len(parts) == 2:
                addr = parts[1]
                if addr.lower() != token_address.lower():
                    return addr
        return None

    def scout_token(self, token_address, chain_id, symbol=None,
                    name=None, decimals=None):
        """Full pipeline: register token + find best pool.

        Primary: GeckoTerminal (free, deterministic)
        Backup:  Gemini AI (richer analysis, needs API key)
        """
        chain_key = str(chain_id)

        # Register token in DB
        self.registry.add_token(
            address=token_address,
            chain=chain_key,
            symbol=symbol,
            name=name,
            decimals=decimals,
        )

        # Primary: GeckoTerminal
        pool = self.find_best_pool(token_address, chain_id)

        # Backup enrichment: Gemini AI scout
        gemini_data = self._gemini_enrich(token_address, chain_id)
        if gemini_data:
            # If GeckoTerminal found nothing, log Gemini's recommendation
            if not pool:
                print(f"  [Scout] GeckoTerminal found nothing, "
                      f"Gemini suggests: {gemini_data.get('bestSource')}")
            # Store Gemini analysis summary in registry notes
            self.registry.add_token(
                address=token_address,
                chain=chain_key,
                symbol=(gemini_data.get('tokenSymbol') or symbol),
                name=(gemini_data.get('tokenName') or name),
                decimals=decimals,
            )

        return pool

    def _gemini_enrich(self, token_address, chain_id):
        """Optional Gemini AI enrichment. Returns analysis or None."""
        if not _GEMINI_AVAILABLE:
            return None

        cache_key = (token_address.lower(), str(chain_id))
        if cache_key in self._gemini_cache:
            ts, result = self._gemini_cache[cache_key]
            if time.time() - ts < CACHE_TTL:
                return result

        try:
            result = gemini_scout.scout_liquidity(
                token_address, chain_id)
            self._gemini_cache[cache_key] = (time.time(), result)
            return result
        except Exception as e:
            print(f"  [GeminiScout] Enrichment failed: {e}")
            return None

    def get_token_price_usd(self, token_address, chain_id, pool=None):
        """Get current token price in USD from its trading pool via
        GeckoTerminal pool endpoint.

        Args:
            token_address: Token contract address
            chain_id: Chain ID (int)
            pool: Pool dict from registry (optional, fetched if None)

        Returns:
            float price in USD, or None if unavailable
        """
        token_address = token_address.lower()
        chain_key = str(chain_id)

        if pool is None:
            pool = self.registry.get_best_pool(token_address, chain_key)
        if not pool or not pool.get('pool_address'):
            return None

        network = NETWORK_MAP.get(chain_id)
        if not network:
            return None

        return self._fetch_pool_token_price(
            pool['pool_address'], network, token_address)

    def _fetch_pool_token_price(self, pool_address, network,
                                token_address):
        """Fetch current token price from GeckoTerminal pool data."""
        url = (f"{GECKO_API}/networks/{network}/pools/"
               f"{pool_address}")
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 429:
                time.sleep(5)
                resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            data = resp.json()
            attrs = data.get("data", {}).get("attributes", {})
            rels = data.get("data", {}).get("relationships", {})

            # Determine if our token is base or quote in this pool
            base_id = (rels.get("base_token", {})
                       .get("data", {}).get("id", ""))
            base_addr = (base_id.split("_", 1)[-1].lower()
                         if "_" in base_id else "")

            if base_addr == token_address.lower():
                price_str = attrs.get("base_token_price_usd")
            else:
                price_str = attrs.get("quote_token_price_usd")

            if price_str:
                price = float(price_str)
                if price > 0:
                    return price
        except Exception as e:
            print(f"  [Scout] Pool price error: {e}")
        return None

    def get_gemini_analysis(self, token_address, chain_id):
        """Public access to Gemini analysis for dashboard/API use."""
        return self._gemini_enrich(token_address, chain_id)
