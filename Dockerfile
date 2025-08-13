FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .
ENV PYTHONUNBUFFERED=1 QI_LOG_DIR=/app/live_output
VOLUME ["/app/live_output"]
HEALTHCHECK CMD python scripts/healthcheck.py || exit 1
CMD ["qi","run","--cfg","qi.yaml"]
