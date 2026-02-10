FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY GROUPS_INDEX_TEMPLATE.json .

# Set PYTHONPATH
ENV PYTHONPATH=/app

CMD ["python", "app/main.py"]
