FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

# Run as non-root
RUN useradd -m bridge && chown -R bridge:bridge /app
USER bridge

CMD ["python", "-u", "app/main.py"]
