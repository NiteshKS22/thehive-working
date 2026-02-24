FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

RUN useradd -m api && chown -R api:api /app
USER api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
