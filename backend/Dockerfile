FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Forma shell (no exec) para que ${PORT} se expanda: localmente no se define y
# usa 8000 (igual que antes); en Render, que asigna su propio puerto dinamico,
# el contenedor tiene que escuchar ahi si o si.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload

