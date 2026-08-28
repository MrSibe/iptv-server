import logging
from typing import Dict, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.responses import StreamingResponse as FastapiStreamingResponse
from starlette.middleware.cors import CORSMiddleware

from app.database.connection import init_db
from app.utils.m3u8_generator import M3U8Generator
from app.services.config_manager import channel_config
from app.services.proxy_service import ProxyService, init_session, close_session

logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
logger = logging.getLogger(__name__)

m3u8_generator = M3U8Generator()

app = FastAPI(
    title="IPTV Server",
    description="IPTV M3U8 Streaming Server",
    version="0.1.0"
)

@app.get("/", tags=["welcome"])
async def root():
    return {
        "message": "Welcome to IPTV Server!",
        "endpoints": {
            "health_check": "/health",
            "playlist_m3u": "/playlist.m3u",
            "playlist_json": "/channels.json",
            "api_docs": "/docs"
        },
        "version": "0.1.0"
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_conn = None

@app.on_event("startup")
async def startup():
    global db_conn

    await init_session()
    logger.info("[Server] HTTP connection pool initialized.")

    db_conn = await init_db()
    logger.info("[Server] Database initialized.")

    await channel_config.start(db_conn)
    logger.info("[Server] Channel config manager started.")

@app.on_event("shutdown")
async def shutdown():
    global db_conn

    await channel_config.stop()
    db_conn = None

    await close_session()
    logger.info("[Server] HTTP connection pool closed.")

@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}

@app.get("/playlist.m3u8", tags=["playlist"])
async def get_playlist_m3u8(request: Request):
    channels = channel_config.channels
    m3u8_content = m3u8_generator.generate_m3u8(channels, str(request.base_url))
    return PlainTextResponse(content=m3u8_content, media_type="audio/x-mpegurl")

@app.get("/channels.json", tags=["playlist"])
async def get_channels_json():
    channels = channel_config.channels
    return [ch.model_dump() for ch in channels]

def _get_base_directory(url: str) -> str:
    base = url.rstrip('/')
    if base.endswith('.m3u8'):
        return base.rsplit('/', 1)[0] + '/'
    return base + '/'

def _extract_forwarded_headers(request: Request) -> Dict[str, str]:
    keys_to_forward = ['range', 'referer', 'origin', 'cookie']
    result = {}
    for key in keys_to_forward:
        value = request.headers.get(key)
        if value:
            result[key] = value
    return result

@app.get("/proxy/{channel_id}", tags=["proxy"])
async def proxy_root(channel_id: str, request: Request):
    return await _handle_proxy_request(channel_id, "", request)

@app.get("/proxy/{channel_id}/{path:path}", tags=["proxy"])
async def proxy_with_path(channel_id: str, path: str, request: Request):
    return await _handle_proxy_request(channel_id, path, request)

async def _handle_proxy_request(
    channel_id: str,
    path: str,
    request: Request
):
    channel = channel_config.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
    mode = getattr(channel, 'mode', 'proxy')
    if mode == 'direct':
        raise HTTPException(
            status_code=302,
            headers={"Location": channel.url}
        )
    if not path or path == "index.m3u8":
        upstream_url = channel.url
        forwarded = _extract_forwarded_headers(request)
        logger.info(f"[Proxy] [PLAYLIST] Fetching {upstream_url}")
        return await ProxyService.transform_m3u8(
            upstream_url=upstream_url,
            server_host=str(request.base_url),
            channel_id=channel_id,
            headers=forwarded if forwarded else None
        )
    elif path.endswith(".ts"):
        upstream_url = _get_base_directory(channel.url) + path
        forwarded = _extract_forwarded_headers(request)
        logger.info(f"[Proxy] [TS] Streaming {upstream_url}")
        return await ProxyService.stream(
            upstream_url=upstream_url,
            request_headers=forwarded if forwarded else None
        )
    else:
        logger.warning(f"[Proxy] BLOCKED: {channel_id}/{path} - Unauthorized type")
        raise HTTPException(
            status_code=403,
            detail="Unauthorized file type. Only .ts files are allowed."
        )

@app.get("/favicon.ico")
async def favicon():
    return None