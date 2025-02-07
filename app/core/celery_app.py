import logging

from celery import Celery

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

celery_app = Celery(
    'worker',
    broker='redis://redis:6379/0',  # Docker Compose에서 Redis 서비스 이름 사용
    backend='redis://redis:6379/0',
    include=["app.tasks.tasks"]  # Celery 작업이 정의된 모듈
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True
)

celery_app.conf.beat_schedule = {
    "fetch-stock-data-every-10-minutes": {
        "task": "app.tasks.tasks.fetch_stock_data",
        "schedule": 600.0,  # 10분마다 실행
        "args": ("AAPL",)  # 작업에 전달할 인자
    },
}


