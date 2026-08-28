import asyncio
import logging
from typing import Dict, Optional
import aiohttp
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse

logger = logging.getLogger(__name__)

CLIENT_TIMEOUT = aiohttp.ClientTimeout(
    total=120,
    connect=10,
    sock_read=30,
    sock_connect=5
)

CHUNK_SIZE = 64 * 1024

_client_session: Optional[aiohttp.ClientSession] = None

async def init_session():
    global _client_session
    if _client_session is None or _client_session.closed:
        _client_session = aiohttp.ClientSession(timeout=CLIENT_TIMEOUT)
    return _client_session

async def close_session():
    global _client_session
    if _client_session and not _client_session.closed:
        await _client_session.close()

class ProxyStream:
    def __init__(self, resp):
        self.resp = resp
    async def __aiter__(self):
        try:
            async for chunk in self.resp.content.iter_chunked(CHUNK_SIZE):
                yield chunk
        finally:
            self.resp.close()

class ProxyService:
    @classmethod
    async def stream(
        cls,
        upstream_url: str,
        request_headers: Optional[Dict[str, str]] = None
    ) -> StreamingResponse:
        session = await init_session()

        headers = {}
        if request_headers:
            headers.update(request_headers)
        
        try:
            resp = await session.get(upstream_url, headers=headers)
            logger.info(f"[Proxy] Started streaming: {upstream_url}")
            content_type = resp.content_type or 'application/octet-stream'
            responsed_headers = {}
            accept_ranges = resp.headers.get('Accept-Ranges')
            if accept_ranges:
                responsed_headers['Accept-Ranges'] = accept_ranges
            return StreamingResponse(
                content=ProxyStream(resp),
                media_type=content_type,
                headers=responsed_headers
            )

        except aiohttp.ClientConnectorError as e:
            logger.error(f"[Proxy] Cannot connect to upstream: {e}")
            raise HTTPException(status_code=502, detail=f"Upstream unreachable: {str(e)}")
        except asyncio.TimeoutError:
            logger.error(f"[Proxy] Timeout fetching: {upstream_url}")
            raise HTTPException(status_code=504, detail="Upstream request timed out")
        
    @classmethod
    async def transform_m3u8(
        cls,
        upstream_url: str,
        server_host: str,
        channel_id: str,
        headers: Optional[Dict[str, str]] = None
    ) -> StreamingResponse:
        session = await init_session()
        try:
            async with session.get(upstream_url, headers=headers) as resp:
                raw_content = await resp.text()
                transformed_lines = cls._parse_and_transform_m3u8(
                    lines=raw_content.splitlines(),
                    server_base=server_host.rstrip('/'),
                    channel_id=channel_id,
                    source_playlist_url=upstream_url
                )
                transformed_content = "\n".join(transformed_lines)
                logger.info(f"[Proxy] Transformed M3U8 for {channel_id}: {len(transformed_lines)} lines")
                return PlainTextResponse(
                    content=transformed_content,
                    media_type="application/vnd.apple.mpegurl",
                    headers={"Content-Disposition": 'inline; filename="index.m3u8"'}
                )
        except aiohttp.ClientConnectorError as e:
            logger.error(f"[Proxy] Timeout loading playlist: {upstream_url}")
            raise HTTPException(status_code=502, detail=f"Failed to load playlist: {str(e)}")
        except asyncio.TimeoutError:
            logger.error(f"[Proxy] Timeout loading playlist: {upstream_url}")
            raise HTTPException(status_code=504, detail="Playlist load timed out")
        
    @staticmethod
    def _parse_and_transform_m3u8(
        lines: list[str],
        server_base: str,
        channel_id: str,
        source_playlist_url: str
    ) -> list[str]:
        result = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                result.append(line)
                continue
            url = stripped
            if url.startswith('http://') or url.startswith('https://'):
                if url == source_playlist_url:
                    new_url = f"{server_base}/proxy/{channel_id}/index.m3u8"
                    result.append(new_url)
                else:
                    result.append(url)
                continue
            result.append(url)
        return result
    
    @staticmethod
    def _resolve_relative_path(relative_url: str, base_directory: str) -> str:
        import re
        if relative_url.startswith('/'):
            match = re.match(r'^(https?://[^/]+)(/.*)$', relative_url)
            if match:
                return match.group(2)
        combined = f"{base_directory}/{relative_url}"
        parts = combined.replace('\\','/').split('/')
        clean_parts = []
        for part in parts:
            if part == '' or part == '.':
                continue
            elif part == '..':
                if clean_parts and clean_parts[-1] != '..':
                    clean_parts.pop()
            else:
                clean_parts.append(part)

        return '/'.join(clean_parts)