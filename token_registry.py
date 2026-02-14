#!/usr/bin/env python3
"""
TOKEN REGISTRY — SQLite cache for discovered tokens and their best pools.
Used by LiquidityScout and AutonomousTrader to avoid redundant API calls.
"""

import sqlite3
import threading
from datetime import datetime, timedelta

DB_PATH = "/home/sauly/hummingbot/data/token_registry.db"
POOL_STALE_HOURS = 24  # re-scout pools older than this


class TokenRegistry:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tokens (
                address TEXT NOT NULL,
                chain TEXT NOT NULL,
                symbol TEXT,
                name TEXT,
                decimals INTEGER,
                first_seen TEXT,
                last_updated TEXT,
                PRIMARY KEY (address, chain)
            );

            CREATE TABLE IF NOT EXISTS pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT NOT NULL,
                pool_address TEXT NOT NULL,
                dex TEXT,
                fee_tier INTEGER,
                quote_token TEXT,
                quote_token_address TEXT,
                liquidity_usd REAL,
                volume_24h REAL,
                chain TEXT NOT NULL,
                last_updated TEXT,
                UNIQUE(token_address, pool_address, chain)
            );

            CREATE INDEX IF NOT EXISTS idx_pools_token
                ON pools(token_address, chain);
            CREATE INDEX IF NOT EXISTS idx_pools_liquidity
                ON pools(liquidity_usd DESC);
        """)
        conn.commit()

    # -- Token operations --

    def add_token(self, address, chain, symbol=None, name=None, decimals=None):
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT INTO tokens (address, chain, symbol, name, decimals,
                                first_seen, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(address, chain) DO UPDATE SET
                symbol = COALESCE(excluded.symbol, tokens.symbol),
                name = COALESCE(excluded.name, tokens.name),
                decimals = COALESCE(excluded.decimals, tokens.decimals),
                last_updated = excluded.last_updated
        """, (address.lower(), chain, symbol, name, decimals, now, now))
        conn.commit()

    def get_token(self, address, chain):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM tokens WHERE address = ? AND chain = ?",
            (address.lower(), chain)
        ).fetchone()
        return dict(row) if row else None

    def get_all_tokens(self, chain=None):
        conn = self._get_conn()
        if chain:
            rows = conn.execute(
                "SELECT * FROM tokens WHERE chain = ? ORDER BY first_seen DESC",
                (chain,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tokens ORDER BY first_seen DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # -- Pool operations --

    def add_pool(self, token_address, pool_address, chain, dex=None,
                 fee_tier=None, quote_token=None, quote_token_address=None,
                 liquidity_usd=None, volume_24h=None):
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT INTO pools (token_address, pool_address, chain, dex,
                               fee_tier, quote_token, quote_token_address,
                               liquidity_usd, volume_24h, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_address, pool_address, chain) DO UPDATE SET
                dex = COALESCE(excluded.dex, pools.dex),
                fee_tier = COALESCE(excluded.fee_tier, pools.fee_tier),
                quote_token = COALESCE(excluded.quote_token, pools.quote_token),
                quote_token_address = COALESCE(excluded.quote_token_address,
                                               pools.quote_token_address),
                liquidity_usd = COALESCE(excluded.liquidity_usd,
                                         pools.liquidity_usd),
                volume_24h = COALESCE(excluded.volume_24h, pools.volume_24h),
                last_updated = excluded.last_updated
        """, (token_address.lower(), pool_address.lower(), chain, dex,
              fee_tier, quote_token, quote_token_address,
              liquidity_usd, volume_24h, now))
        conn.commit()

    def get_best_pool(self, token_address, chain):
        """Get the highest-liquidity pool for a token. Returns None if stale."""
        conn = self._get_conn()
        row = conn.execute("""
            SELECT * FROM pools
            WHERE token_address = ? AND chain = ?
            ORDER BY liquidity_usd DESC
            LIMIT 1
        """, (token_address.lower(), chain)).fetchone()

        if not row:
            return None

        pool = dict(row)
        # Check staleness
        updated = datetime.fromisoformat(pool['last_updated'])
        if datetime.utcnow() - updated > timedelta(hours=POOL_STALE_HOURS):
            return None  # Force re-scout

        return pool

    def get_pools_for_token(self, token_address, chain):
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM pools
            WHERE token_address = ? AND chain = ?
            ORDER BY liquidity_usd DESC
        """, (token_address.lower(), chain)).fetchall()
        return [dict(r) for r in rows]

    def get_all_pools(self, chain=None):
        conn = self._get_conn()
        if chain:
            rows = conn.execute(
                "SELECT * FROM pools WHERE chain = ? "
                "ORDER BY liquidity_usd DESC", (chain,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pools ORDER BY liquidity_usd DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_tokens_with_pools(self, chain=None):
        """Get all tokens joined with their best pool."""
        conn = self._get_conn()
        query = """
            SELECT t.*, p.pool_address, p.dex, p.fee_tier, p.quote_token,
                   p.quote_token_address, p.liquidity_usd, p.volume_24h,
                   p.last_updated AS pool_updated
            FROM tokens t
            LEFT JOIN pools p ON t.address = p.token_address
                AND t.chain = p.chain
                AND p.id = (
                    SELECT id FROM pools p2
                    WHERE p2.token_address = t.address
                      AND p2.chain = t.chain
                    ORDER BY liquidity_usd DESC LIMIT 1
                )
        """
        if chain:
            query += " WHERE t.chain = ? ORDER BY t.first_seen DESC"
            rows = conn.execute(query, (chain,)).fetchall()
        else:
            query += " ORDER BY t.first_seen DESC"
            rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
