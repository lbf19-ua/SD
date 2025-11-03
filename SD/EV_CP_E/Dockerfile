# ============================================================================
# Dockerfile para EV_CP_E (Engine + TCP Health Server + CLI + Kafka)
# ============================================================================
FROM python:3.11-slim

# Metadatos
LABEL maintainer="EV Charging System"
LABEL description="EV Charging Point Engine with TCP health server, CLI menu and Kafka support"

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV CP_ID=CP_001
ENV LOCATION="Default Location"
ENV HEALTH_PORT=5100
# KAFKA_BROKER se pasa desde docker-compose (.env file)
# ENV KAFKA_BROKER=localhost:9092  # ⚠️ NO usar - debe venir de .env en despliegue multi-PC

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

# Copiar archivos del componente EV_CP_E
COPY EV_CP_E/ /app/

# Crear directorio para la base de datos
RUN mkdir -p /app/data

# Exponer puerto TCP para health checks
EXPOSE ${HEALTH_PORT}

# Healthcheck (verificar que el TCP server responde)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', ${HEALTH_PORT})); s.sendall(b'STATUS?\n'); response=s.recv(100); s.close(); exit(0 if response==b'OK' else 1)" || exit 1

# Comando por defecto (usa variables de entorno)
# Las variables CP_ID, LOCATION, HEALTH_PORT, KAFKA_BROKER se pasan desde docker-compose
CMD ["python", "-u", "EV_CP_E.py"]
