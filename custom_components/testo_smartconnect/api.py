"""Read-only, asynchronous Testo Smart Connect client (no device mutations)."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import aiohttp

ENDPOINTS = {
    "properties": "/v3/devices/properties",
    "status": "/v4/devices/status",
    "measurements": "/v2/measurements",
    "objects": "/v1/measuring-objects",
    "locations": "/v1/locations",
    "alarms": "/v3/alarms",
}
MAX_BYTES = 20 * 1024 * 1024


class ApiError(Exception):
    """Safe error without credentials, URLs or response bodies."""


class AuthenticationError(ApiError):
    """Key invalid/expired."""


class QuotaError(ApiError):
    """Local budget or upstream quota reached."""


def parse_csv(raw: bytes) -> list[dict[str, str]]:
    """Decode bytes explicitly; empty exports are valid."""
    try:
        text = raw.decode("utf-8-sig")
        if not text.strip():
            return []
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or len(reader.fieldnames) < 2:
            raise ValueError("Not tabular CSV")
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError("Malformed CSV")
        return rows
    except (UnicodeError, csv.Error, ValueError) as err:
        raise ApiError("Invalid CSV result") from err


def safe_download_url(url: str) -> bool:
    """Only Testo's documented HTTPS S3 result storage; no arbitrary hosts."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    return (
        parts.scheme == "https"
        and parts.username is None
        and parts.password is None
        and parts.port in (None, 443)
        and host.startswith("tds-")
        and ".s3" in host
        and host.endswith(".amazonaws.com")
    )


class TestoApi:
    """Session is owned by HA. Never attach API credentials to storage requests."""

    def __init__(self, session, key, region="eu", budget=None, save_budget=None):
        if region not in ("eu", "am", "ap"):
            raise ValueError("Unsupported region")
        self.session = session
        self.base = f"https://data-api.{region}.smartconnect.testo.com"
        self._key = key
        self.budget = budget if budget is not None else {}
        self.save_budget = save_budget
        self.pending: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self.block_until = 0.0

    async def _reserve(self):
        month = datetime.now(UTC).strftime("%Y-%m")
        if self.budget.get("month") != month:
            self.budget.update(month=month, posts=0, blocked=False)
        if self.budget.get("blocked") or self.budget.get("posts", 0) >= 9500:
            raise QuotaError("Monthly API budget reached")
        self.budget["posts"] = self.budget.get("posts", 0) + 1
        if self.save_budget:
            await self.save_budget()

    async def _request(self, method, url, body=None, storage=False):
        if asyncio.get_running_loop().time() < self.block_until:
            raise ApiError("API cooldown active")
        headers = {} if storage else {"x-custom-api-key": self._key}
        try:
            async with self.session.request(
                method,
                url,
                headers=headers,
                json=body,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=45),
            ) as response:
                if response.status == 401 and not storage:
                    raise AuthenticationError("Invalid or expired API key")
                if response.status == 403 and not storage:
                    # Distinguish permissions from quota using body internally only.
                    data = await response.content.read(8192)
                    if b"maximum allowed" in data or b"10000" in data:
                        self.budget["blocked"] = True
                        if self.save_budget:
                            await self.save_budget()
                        raise QuotaError("Testo monthly quota reached")
                    raise ApiError("API access denied (403)")
                if response.status == 429:
                    self.block_until = asyncio.get_running_loop().time() + 300
                    raise ApiError("Rate limited; five minute cooldown")
                if response.status != 200 and response.status != 202:
                    raise ApiError(f"HTTP {response.status}")
                chunks = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_BYTES:
                        raise ApiError("Result exceeds 20 MiB safety limit")
                if storage:
                    return bytes(chunks)
                result = json.loads(chunks)
                if not isinstance(result, dict):
                    raise ApiError("Invalid API response")
                return result
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise ApiError("Network or response decoding error") from None

    async def query(self, kind: str, start=None, end=None) -> list[dict[str, Any]]:
        """Submit once, bounded polling, download ALL parts. Resume pending jobs."""
        async with self._lock:
            endpoint = ENDPOINTS[kind]
            if kind not in self.pending:
                await self._reserve()
                body: dict[str, Any] = {"options": {"result_file_format": "CSV"}}
                if kind in ("measurements", "alarms"):
                    if start:
                        body["date_time_from"] = start
                    if end:
                        body["date_time_until"] = end
                submitted = await self._request("POST", self.base + endpoint, body)
                try:
                    self.pending[kind] = str(UUID(submitted["request_uuid"]))
                except (KeyError, ValueError, TypeError) as err:
                    raise ApiError("Missing request UUID") from err
            request_id = self.pending[kind]
            for wait in (3, 5, 10, 20, 30, 30):
                await asyncio.sleep(wait)
                status = await self._request("GET", f"{self.base}{endpoint}/{request_id}")
                if status.get("status") == "Completed":
                    break
                if status.get("status") not in ("Submitted", "In Progress"):
                    self.pending.pop(kind, None)
                    raise ApiError("Unexpected asynchronous job status")
            else:
                raise ApiError("Result still pending; will resume next refresh")
            urls = status.get("data_urls")
            if not isinstance(urls, list) or len(urls) > 100:
                raise ApiError("Invalid result file list")
            rows = []
            for url in urls:
                if not isinstance(url, str) or not safe_download_url(url):
                    raise ApiError("Unsupported result storage host")
                raw = await self._request("GET", url, storage=True)
                rows.extend(parse_csv(raw))
                if len(rows) > 100000:
                    raise ApiError("Result exceeds 100000 row safety limit")
            self.pending.pop(kind, None)
            return rows
