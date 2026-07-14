FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
COPY . .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/install/bin:$PATH \
    PYTHONPATH=/install/lib/python3.11/site-packages:/app/src \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0
RUN apt-get update && apt-get install -y --no-install-recommends wget curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system --gid 1001 bo && \
    useradd --system --uid 1001 --gid bo --no-create-home bo
COPY --from=builder /install /install
COPY --from=builder /build /app
RUN chown -R bo:bo /app
USER bo
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8501/_stcore/health || exit 1
CMD ["streamlit", "run", "src/back_office_ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]