import asyncio
import cProfile
import json
import logging
import time  # time 모듈 import
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from app.api import stocks

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ],
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 실행할 코드
    logger.info("Starting up the FastAPI application")
    yield
    # 애플리케이션 종료 시 실행할 코드
    logger.info("Shutting down the FastAPI application")

app = FastAPI(lifespan=lifespan)

# WebSocket 클라이언트 관리 클래스
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(f"Completed in {process_time:.2f}ms")

    if isinstance(response, StreamingResponse):
        logger.debug(f"Response: {response.status_code} - StreamingResponse")
    else:
        logger.debug(f"Response: {response.status_code}")

    return response

@app.exception_handler(Exception)
async def validation_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": f"An internal server error occurred: {str(exc)}"},
    )
@app.websocket("/ws/stocks")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            request_data = json.loads(data)

            # 주식 데이터를 처리 및 응답
            stock_data = await fetch_real_time_stock_data(request_data["symbol"])
            await manager.send_personal_message(stock_data, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("A client disconnected")

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # 여기에 알림 처리 로직을 추가합니다.
            await websocket.send_text(f"Alert received: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")

async def fetch_real_time_stock_data(symbol: str):
    # 여기에 주식 데이터를 실시간으로 가져오는 로직을 추가합니다.
    # 예제 응답:
    return json.dumps({
        "symbol": symbol,
        "price": 150.00,
        "volume": 10000
    })

app.include_router(stocks.router, prefix="/api/v1")

if __name__ == "__main__":
    # 프로파일링 시작
    cProfile.run('asyncio.run(execute_optimized_fetch())')
