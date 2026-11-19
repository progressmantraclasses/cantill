FROM python:3.11-slim
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY data/ ./data/
ENV DATA_DIR=/srv/data PYTHONUNBUFFERED=1
WORKDIR /srv/backend
EXPOSE 8000
# Flask app served by uvicorn through the ASGI wrapper; tables + seed data are created on first start.
CMD ["sh", "-c", "uvicorn app.asgi:application --host 0.0.0.0 --port ${PORT:-8000}"]
