# app/core/session.py

import aiohttp
from aiohttp import ClientSession


async def get_session() -> ClientSession:
    """비동기적으로 HTTP 세션을 생성합니다."""
    conn = aiohttp.TCPConnector(limit=100)  # 최대 100개의 연결을 재사용
    session = aiohttp.ClientSession(connector=conn)
    return session

async def close_session(session: ClientSession):
    """비동기적으로 세션을 종료합니다."""
    await session.close()

