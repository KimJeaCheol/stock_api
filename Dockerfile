FROM python:3.10-slim

WORKDIR /app

# TA-Lib 설치 (C 라이브러리 빌드 후 Python 바인딩)
RUN apt-get update && apt-get install -y \
    build-essential gcc make wget \
    && wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib-0.4.0 && ./configure --prefix=/usr && make && make install \
    && cd .. && rm -rf ta-lib-0.4.0* \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
