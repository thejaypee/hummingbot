#!/usr/bin/env python3
"""
WHITELIST MANAGER — Controls which sender addresses are trusted.

Tokens arriving from whitelisted addresses are automatically whitelisted
for trading. The whitelist is persisted to SQLite alongside the token
registry so it survives restarts.

Flow:
  1. Admin adds trusted sender addresses (e.g., deployer wallets, bridges)
  2. When a Transfer event arrives FROM a whitelisted sender TO our wallet,
     the token is auto-whitelisted for the chain it arrived on
  3. Auto-whitelisted tokens proceed through the pipeline:
     chain detection → liquidity scout → order → monitor
"""

import sqlite3
import threading
from datetime import datetime

DB_PATH = "/home/sauly/hummingbot/data/token_registry.db"


class WhitelistManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS whitelisted_senders (
                address TEXT NOT NULL PRIMARY KEY,
                label TEXT,
                added_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS whitelisted_tokens (
                address TEXT NOT NULL,
                chain_id INTEGER NOT NULL,
                symbol TEXT,
                sender TEXT,
                auto_whitelisted INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                added_at TEXT NOT NULL,
                PRIMARY KEY (address, chain_id)
            );

            CREATE TABLE IF NOT EXISTS token_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT NOT NULL,
                chain_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                amount TEXT,
                block_number INTEGER,
                tx_hash TEXT,
                event_type TEXT DEFAULT 'transfer_in',
                timestamp TEXT NOT NULL
            );
        """)
        conn.commit()

    # -- Sender whitelist --

    def add_sender(self, address, label=None):
        """Add a trusted sender address."""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO whitelisted_senders (address, label, added_at)
            VALUES (?, ?, ?)
        """, (address.lower(), label, datetime.utcnow().isoformat()))
        conn.commit()

    def remove_sender(self, address):
        """Remove a sender from whitelist."""
        conn = self._get_conn()
        conn.execute("DELETE FROM whitelisted_senders WHERE address = ?",
                     (address.lower(),))
        conn.commit()

    def is_sender_whitelisted(self, address):
        """Check if a sender address is whitelisted."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM whitelisted_senders WHERE address = ?",
            (address.lower(),)
        ).fetchone()
        return row is not None

    def get_all_senders(self):
        """Get all whitelisted sender addresses."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM whitelisted_senders ORDER BY added_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Token whitelist (auto-populated from arrivals) --

    def whitelist_token(self, token_address, chain_id, symbol=None,
                        sender=None, auto=True):
        """Whitelist a token for trading on a specific chain."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO whitelisted_tokens
                (address, chain_id, symbol, sender, auto_whitelisted,
                 status, added_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            ON CONFLICT(address, chain_id) DO UPDATE SET
                symbol = COALESCE(excluded.symbol, whitelisted_tokens.symbol),
                sender = COALESCE(excluded.sender, whitelisted_tokens.sender),
                status = CASE
                    WHEN whitelisted_tokens.status = 'blocked' THEN 'blocked'
                    ELSE 'pending'
                END
        """, (token_address.lower(), chain_id, symbol, sender.lower() if sender else None,
              1 if auto else 0, datetime.utcnow().isoformat()))
        conn.commit()

    def is_token_whitelisted(self, token_address, chain_id):
        """Check if token is whitelisted and not blocked."""
        conn = self._get_conn()
        row = conn.execute("""
            SELECT status FROM whitelisted_tokens
            WHERE address = ? AND chain_id = ? AND status != 'blocked'
        """, (token_address.lower(), chain_id)).fetchone()
        return row is not None

    def set_token_status(self, token_address, chain_id, status):
        """Set token status: pending, active, completed, blocked."""
        conn = self._get_conn()
        conn.execute("""
            UPDATE whitelisted_tokens SET status = ?
            WHERE address = ? AND chain_id = ?
        """, (status, token_address.lower(), chain_id))
        conn.commit()

    def get_pending_tokens(self, chain_id=None):
        """Get tokens awaiting processing (liquidity scout → order)."""
        conn = self._get_conn()
        if chain_id:
            rows = conn.execute("""
                SELECT * FROM whitelisted_tokens
                WHERE status = 'pending' AND chain_id = ?
                ORDER BY added_at ASC
            """, (chain_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM whitelisted_tokens
                WHERE status = 'pending'
                ORDER BY added_at ASC
            """).fetchall()
        return [dict(r) for r in rows]

    def get_active_tokens(self, chain_id=None):
        """Get tokens currently being traded."""
        conn = self._get_conn()
        if chain_id:
            rows = conn.execute("""
                SELECT * FROM whitelisted_tokens
                WHERE status = 'active' AND chain_id = ?
            """, (chain_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM whitelisted_tokens WHERE status = 'active'
            """).fetchall()
        return [dict(r) for r in rows]

    def get_all_whitelisted_tokens(self, chain_id=None):
        """Get all whitelisted tokens (any status except blocked)."""
        conn = self._get_conn()
        if chain_id:
            rows = conn.execute("""
                SELECT * FROM whitelisted_tokens
                WHERE chain_id = ? AND status != 'blocked'
                ORDER BY added_at DESC
            """, (chain_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM whitelisted_tokens
                WHERE status != 'blocked'
                ORDER BY added_at DESC
            """).fetchall()
        return [dict(r) for r in rows]

    def get_all_tokens(self, chain_id=None):
        """Alias for get_all_whitelisted_tokens (used by API server)."""
        return self.get_all_whitelisted_tokens(chain_id)

    # -- Event log --

    def log_event(self, token_address, chain_id, sender,
                  amount=None, block_number=None, tx_hash=None,
                  event_type='transfer_in'):
        """Log a token transfer event for audit trail."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO token_events
                (token_address, chain_id, sender, amount, block_number,
                 tx_hash, event_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (token_address.lower(), chain_id, sender.lower(),
              str(amount) if amount else None, block_number,
              tx_hash, event_type, datetime.utcnow().isoformat()))
        conn.commit()

    def get_events(self, chain_id=None, limit=50):
        """Get recent events for dashboard display."""
        conn = self._get_conn()
        if chain_id:
            rows = conn.execute("""
                SELECT * FROM token_events
                WHERE chain_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (chain_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM token_events
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]
