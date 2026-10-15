from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.files.indexer import index_tree
from app.files.service import FileService

logger = logging.getLogger(__name__)


async def scan_forever(files: FileService, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(index_tree, files)
        except Exception:
            logger.exception("Falha na varredura periódica")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.scan_interval_seconds)
        except asyncio.TimeoutError:
            pass
