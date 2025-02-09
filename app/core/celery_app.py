import logging

from celery import Celery

from app.core.logging import logger  # 이미 설정된 logger import

celery_app = Celery(
    'worker',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=["app.tasks.tasks"]  # ✅ Celery가 동적으로 태스크를 찾도록 설정
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True
)
