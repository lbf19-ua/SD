# ============================================================================
# Dockerfile para EV_Central (WebSocket + Kafka)
# ============================================================================
FROM python:3.11-slim

# Metadatos
LABEL maintainer="EV Charging System"
LABEL description="EV Central Server with WebSocket and Kafka support"

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV CENTRAL_PORT=5000
ENV WS_PORT=8002

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero (para aprovechar cache de Docker)
COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar archivos de configuración
COPY ../network_config.py /app/network_config.py
COPY ../database.py /app/database.py
COPY ../event_utils.py /app/event_utils.py

# Copiar archivos del componente
COPY . /app/EV_Central/

# Crear directorio para la base de datos
RUN mkdir -p /app/data

# Exponer puertos
EXPOSE 5000 8002

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 5000)); s.close()" || exit 1

# Comando por defecto (WebSocket version)
CMD ["python", "/app/EV_Central/EV_Central_WebSocket.py"]