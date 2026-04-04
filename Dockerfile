# Stage 1: 의존성 빌드 (gcc 등 빌드 툴 포함)
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# 가상환경에 의존성 설치
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: 런타임 (gcc 없음, venv만 복사)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

# 빌드 스테이지의 venv만 복사
COPY --from=builder /venv /venv

# 애플리케이션 코드 복사
COPY app/ ./app/

# 보안: non-root 유저로 실행
RUN adduser --disabled-password --gecos "" elena
USER elena

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
