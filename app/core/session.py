# app/core/session.py
import aiohttp
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def setup_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

async def get_session():
    conn = aiohttp.TCPConnector(limit=100)
    session = aiohttp.ClientSession(connector=conn)
    return session

async def close_session(session: aiohttp.ClientSession):
    await session.close()

session = setup_session()