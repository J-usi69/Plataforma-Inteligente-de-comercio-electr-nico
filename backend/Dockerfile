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

# Forma shell para que ${PORT} se expanda (Railway asigna el suyo; localmente 8000), con exec
# para que uvicorn reciba las señales de apagado. Producción: sin --reload (vigila archivos y
# corre un solo proceso) y con varios workers; WEB_CONCURRENCY permite ajustarlos sin rebuild.
# --proxy-headers: detrás del proxy de Railway, la IP real del cliente viene en X-Forwarded-For.
# Para desarrollo con recarga en caliente, docker-compose.yml sobreescribe este comando.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips "*" --no-access-log

