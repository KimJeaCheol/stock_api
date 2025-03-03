import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


def setup_logging():
    log_dir = "log"  # 로그 디렉토리 설정
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)  # 로그 디렉토리가 없으면 생성

    # 🔹 날짜별 로그 파일 설정 (YYYY-MM-DD.log)
    log_file = os.path.join(log_dir, f"app-{datetime.now().strftime('%Y-%m-%d')}.log")

    file_handler = TimedRotatingFileHandler(
        log_file,  # 로그 파일 이름 (기본적으로 `app.log`)
        when="midnight",  # 자정(00:00)마다 새로운 파일 생성
        interval=1,  # 1일마다 새로운 파일
        backupCount=7,  # 7일 동안 로그 보관
        encoding="utf-8",
        utc=True,  # UTC 기준으로 날짜 변경 (로컬 시간이 필요하면 False)
    )

    file_handler.suffix = "%Y-%m-%d"  # 파일명에 날짜 추가 (자동으로 `app.log.YYYY-MM-DD` 형식으로 변경)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    # 🔹 콘솔 출력 핸들러
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    # 🔹 기존 핸들러 제거 후 새 핸들러 추가
    logger = logging.getLogger()
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)  # 콘솔 출력 추가
    logger.addHandler(file_handler)  # 날짜별 파일 출력 추가

    # 🔹 `financetoolkit`이 `logging`을 차단하지 않도록 설정
    logging.disable(logging.NOTSET)  # 🚀 모든 로그 다시 활성화

    return logger

# 애플리케이션 시작 시점에만 호출
logger = setup_logging()
