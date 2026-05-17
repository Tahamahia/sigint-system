"""
API Bridge — Push decoded metadata to the Node.js backend.
"""
import asyncio
import json
import os
from typing import Dict, Optional
import aiohttp
import structlog

log = structlog.get_logger()

class APIBridge:
    def __init__(self, backend_url: str, ws_url: str):
        self.backend_url = backend_url.rstrip('/')
        self.ws_url = ws_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._batch: list = []
        self._batch_size = 10
        self._retry_delay = 1
        self._max_retries = 5

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _post(self, path: str, data: dict, retries: int = 0) -> bool:
        try:
            session = await self._get_session()
            url = f"{self.backend_url}{path}"
            async with session.post(url, json=data) as resp:
                if resp.status in (200, 201):
                    return True
                else:
                    body = await resp.text()
                    log.warning("api.post_failed", path=path, status=resp.status, body=body[:200])
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if retries < self._max_retries:
                delay = self._retry_delay * (2 ** retries)
                log.warning("api.retry", path=path, attempt=retries+1, delay=delay)
                await asyncio.sleep(delay)
                return await self._post(path, data, retries + 1)
            log.error("api.post_exhausted", path=path, error=str(e))
            return False

    async def register_sdr(self, device) -> bool:
        return await self._post("/api/sdr/register", {
            "serial": device.serial,
            "device_type": device.device_type,
            "sample_rate": device.sample_rate,
            "gain_db": device.gain_db,
        })

    async def log_signal(self, signal_data: dict) -> bool:
        return await self._post("/api/signals", signal_data)

    async def push_metadata(self, metadata: dict) -> bool:
        return await self._post("/api/signals/metadata", metadata)

    async def push_gps(self, gps_data: dict) -> bool:
        return await self._post("/api/gps", gps_data)

    async def update_sdr_status(self, serial: str, status: dict) -> bool:
        return await self._post(f"/api/sdr/{serial}/status", status)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
