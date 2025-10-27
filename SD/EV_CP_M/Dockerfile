# ============================================================================
# Dockerfile para EV_CP_M (Monitor WebSocket + Kafka)
# ============================================================================
FROM python:3.11-slim

# Metadatos
LABEL maintainer="EV Charging System"
LABEL description="EV Charging Point Monitor with WebSocket and Kafka support"

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV WS_PORT=8003

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero (para aprovechar cache de Docker)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar archivos de configuración
COPY network_config.py /app/network_config.py
COPY database.py /app/database.py
COPY event_utils.py /app/event_utils.py

# Copiar archivos del componente EV_CP_M (copiar directamente a /app)
COPY EV_CP_M/ /app/

# Crear directorio para la base de datos
RUN mkdir -p /app/data

# Exponer puerto WebSocket
EXPOSE 8003

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 8003)); s.close()" || exit 1

# Comando por defecto (WebSocket version)
CMD ["python", "EV_CP_M_WebSocket.py"]