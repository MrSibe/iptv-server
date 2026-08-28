import asyncio
import hashlib
from pathlib import Path
from typing import List, Optional
import logging

import aiosqlite

from app.models.channel import Channel
from app.database.connection import init_db, close_db

logger = logging.getLogger(__name__)

DB_DIR = Path("/app/data")
DB_FILE = DB_DIR / "channels.db"

class ChannelConfig:
    def __init__(self):
        self._channels: List[Channel] = []
        self._current_hash: str = ""

    async def start(self, db_conn):
        # self._db = db = db_conn or await init_db()

        channels, fprint = await self._load_and_hash_from_db()
        self._channels = channels
        self._current_hash = fprint

        logger.info(f"[ConfigManager] First load complete. {len(channels)} channels.")
        logger.info(f"[ConfigManager] Initial Config Hash: {fprint[:8]}...")

        self._poll_task = asyncio.create_task(self._db_poller())
        logger.info("[ConfigManager] Database watcher started (interval: 5s).")

    async def stop(self):
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("[ConfigManager] Database watcher stopped.")

        # await close_db(self._db)
        # logger.info("[ConfigManager] Database connection closed.")

    @property
    def channels(self) -> List[Channel]:
        return self._channels
    
    def get_channels_by_group(self, group_name: str) -> List[Channel]:
        return [ch for ch in self._channels if ch.group == group_name]
    
    def get_channel_by_id(self, channel_id: str) -> Optional[Channel]:
        for ch in self._channels:
            if ch.id == channel_id:
                return ch
        return None

    @property
    def total_count(self) -> int:
        return self._total_count
    
    async def _load_and_hash_from_db(self) -> tuple:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(DB_FILE)) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")

            cursor = await db.execute(
                'SELECT id, name, url, mode, "group", logo, enabled, sort_order '
                "FROM channels "
                "WHERE enabled = 1 "
                "ORDER BY sort_order ASC, id ASC"
            )
            rows = await cursor.fetchall()

        data_string = "|".join([
            f"{r[0]}:{r[1]}:{r[2]}:{r[3]}:{r[4]}:{r[5]}:{r[6]}:{r[7]}" for r in rows
        ])

        content_hash = hashlib.sha256(data_string.encode('utf-8')).hexdigest()

        new_channels = [
            Channel(
                id=row[0],
                name=row[1],
                url=row[2],
                mode=row[3],
                group=row[4],
                logo=row[5],
                enabled=row[6],
                sort_order=row[7]
            ) for row in rows
        ]

        if len(new_channels) != len(self._channels):
            logger.info(f"[ConfigManager] Reloaded: {len(new_channels)} channels.")

        return new_channels, content_hash
    
    async def _db_poller(self):
        while True:
            try:
                _, new_hash = await self._load_and_hash_from_db()

                # logger.info(f"[DEBUG] Checking hash: {new_hash[:8]} (cache: {self._current_hash[:8]})")

                if new_hash != self._current_hash:
                    logger.info(f"[ConfigManager] Hash Changed! ({new_hash[:8]} vs {self._current_hash[:8]})")

                    self._channels, self._current_hash = await self._load_and_hash_from_db()
                    logger.info("[ConfigManager] Cache refreshed automatically.")

                await asyncio.sleep(5)

            except asyncio.CancelledError:
                logger.info("[ConfigManager] Poller task cancelled.")
                break
            except Exception as e:
                logger.warning(f"[ConfigManager] Poller error: {e}")
                await asyncio.sleep(5)

channel_config = ChannelConfig()