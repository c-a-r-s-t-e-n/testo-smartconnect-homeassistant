"""HTTP orchestration, credentials separation and bounded retries."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.testo_smartconnect.api import (
    ApiError,
    AuthenticationError,
    QuotaError,
    parse_csv,
    safe_download_url,
)
from custom_components.testo_smartconnect.api import (
    TestoApi as ApiClient,
)


class Content:
    def __init__(self, body):
        self.body = body

    async def read(self, size):
        return self.body[:size]

    async def iter_chunked(self, size):
        yield self.body


class Response:
    def __init__(self, body, status=200):
        self.status = status
        self.content = Content(body if isinstance(body, bytes) else json.dumps(body).encode())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


def test_byte_decoding_and_url_boundaries():
    assert parse_csv(b'\xef\xbb\xbf"sensor_uuid","measurement"\n"s","2.9"')[0]["measurement"] == "2.9"
    assert parse_csv(b"") == []
    assert safe_download_url("https://tds-eu-p-data-storage-query-results.s3.amazonaws.com/file?signature=example")
    for url in (
        "http://tds-x.s3.amazonaws.com/a",
        "https://evil.test/a",
        "https://tds-x.s3.amazonaws.com.evil.test/a",
        "https://user:secret@tds-x.s3.amazonaws.com/a",
    ):
        assert not safe_download_url(url)


@pytest.mark.asyncio
async def test_multipart_download_never_receives_key_and_no_double_scaling():
    session = Session(
        [
            Response({"request_uuid": "00000000-0000-0000-0000-000000000001", "status": "Submitted"}),
            Response(
                {
                    "status": "Completed",
                    "data_urls": ["https://tds-x.s3.amazonaws.com/1", "https://tds-x.s3.amazonaws.com/2"],
                }
            ),
            Response(b"sensor_uuid,channel_no,timestamp,measurement\ns1,0,2026-11-16T20:00:00Z,2.9\n"),
            Response(b"sensor_uuid,channel_no,timestamp,measurement\ns2,0,2026-11-16T20:00:00Z,-19.1\n"),
        ]
    )
    save = AsyncMock()
    client = ApiClient(session, "synthetic-secret", save_budget=save)
    with patch("asyncio.sleep", new=AsyncMock()):
        rows = await client.query("measurements")
    assert [r["measurement"] for r in rows] == ["2.9", "-19.1"]
    assert session.calls[0][2]["headers"] == {"x-custom-api-key": "synthetic-secret"}
    assert all(call[2]["headers"] == {} for call in session.calls[2:])
    assert all(call[2]["allow_redirects"] is False for call in session.calls)
    assert client.budget["posts"] == 1
    save.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_timeout_resumes_without_post():
    session = Session(
        [Response({"request_uuid": "00000000-0000-0000-0000-000000000001"})]
        + [Response({"status": "In Progress"}) for _ in range(6)]
        + [Response({"status": "Completed", "data_urls": []})]
    )
    client = ApiClient(session, "synthetic-secret")
    with patch("asyncio.sleep", new=AsyncMock()):
        with pytest.raises(ApiError, match="pending"):
            await client.query("properties")
        assert await client.query("properties") == []
    assert sum(call[0] == "POST" for call in session.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body", "exception"),
    [
        (401, {}, AuthenticationError),
        (403, {"detail": "maximum allowed number of API calls (10000)"}, QuotaError),
        (429, {}, ApiError),
    ],
)
async def test_http_failures_are_safe(status, body, exception):
    client = ApiClient(Session([Response(body, status)]), "synthetic-secret")
    with pytest.raises(exception) as exc:
        await client.query("properties")
    assert "synthetic-secret" not in str(exc.value)


@pytest.mark.asyncio
async def test_quota_guard_and_month_reset():
    from datetime import UTC, datetime

    budget = {"month": datetime.now(UTC).strftime("%Y-%m"), "posts": 9500}
    client = ApiClient(Session([]), "secret", budget=budget)
    with pytest.raises(QuotaError):
        await client._reserve()
    budget["month"] = "2000-01"
    await client._reserve()
    assert budget["posts"] == 1
