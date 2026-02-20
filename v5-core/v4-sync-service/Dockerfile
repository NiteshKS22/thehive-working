FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Common library is copied into build context by CI
COPY common/ ./common
COPY app/ ./app

ENV PYTHONPATH=/app
CMD ["python", "app/main.py"]
