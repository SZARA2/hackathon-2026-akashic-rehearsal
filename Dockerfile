FROM python:3.12-slim
WORKDIR /app
COPY core.py server.py ./
COPY static ./static
RUN useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser:appuser /data
ENV DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8882
HEALTHCHECK --interval=30s --timeout=4s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8882/health',timeout=3).read()"
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8882"]
