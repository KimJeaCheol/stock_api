# Python 3.10 (로컬 conda와 동일하게 맞춤)
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 빌드 툴 설치 (numpy, pandas 등 C 확장 모듈 대응)
RUN apt-get update && apt-get install -y \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# FastAPI 실행 (main.py는 프로젝트 루트에 있음)
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
