import asyncio
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from app.api.v1 import stocks
from app.core.logging import logger  # 이미 설정된 logger import


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the FastAPI application")
    yield
    logger.info("Shutting down the FastAPI application")
    
    # WebSocket 연결 종료
    for connection in manager.active_connections:
        await connection.close()
    logger.info("All WebSocket connections closed")

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
    logger.info(f"Completed in {time.time() - start_time:.2f}ms")
    return response

@app.exception_handler(Exception)
async def validation_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"message": "Internal server error"})

@app.websocket("/ws/stocks")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            stock_data = await stocks.get_stock_quote(data)
            await manager.send_personal_message(json.dumps(stock_data), websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.include_router(stocks.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
