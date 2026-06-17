FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app/src

RUN python scripts/generate_demo_data.py

ENTRYPOINT ["python", "src/main.py"]
