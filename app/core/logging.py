# app/core/logging.py

import logging
import os


def setup_logging():
    # 로그 파일 경로 설정
    log_dir = "log"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)  # 로그 디렉토리가 없으면 생성

    log_file = os.path.join(log_dir, "app.log")  # 로그 파일 경로 설정
    
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # 콘솔에 로그 출력
            logging.FileHandler(log_file),  # 파일에 로그 저장
        ],
    )
    logger = logging.getLogger()  # 전역 로거 반환
    return logger

# 애플리케이션 시작 시점에만 호출
logger = setup_logging()
