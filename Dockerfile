# =================================================================
# 1단계: TA-Lib를 빌드하기 위한 'builder' 스테이지
# =================================================================
FROM python:3.10-slim AS builder

# 빌드에 필요한 도구 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    wget

# TA-Lib 소스 다운로드 및 빌드
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make \
    && make install

# =================================================================
# 2단계: 최종 애플리케이션 이미지를 만드는 'final' 스테이지
# =================================================================
FROM python:3.10-slim

WORKDIR /app

# builder 스테이지에서 빌드된 TA-Lib 라이브러리 파일만 복사
COPY --from=builder /usr/lib/libta_lib* /usr/lib/
COPY --from=builder /usr/include/ta-lib/* /usr/include/

# apt 캐시 정리 (필요 시)
RUN rm -rf /var/lib/apt/lists/*

# 파이썬 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]