# Python 3.8 이미지를 베이스로 사용
FROM python:3.8-slim


# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일들을 컨테이너로 복사
COPY . .

# Celery 및 종속성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1

# Celery 작업자를 실행
CMD ["celery", "-A", "core.celery_app.celery_app", "worker", "--loglevel=INFO"]
