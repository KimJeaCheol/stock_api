# 운영 배포용 Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 필수 빌드 툴 설치 (pandas, numpy 등 C 기반 라이브러리 대응)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY . .

# Uvicorn 실행 (FastAPI)
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
