# Dockerfile para EV_CP_M (Monitor)
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar archivos necesarios
COPY . /app/
COPY ../network_config.py /app/network_config.py

# Instalar dependencias de Python
RUN pip install --no-cache-dir kafka-python

# Variables de entorno por defecto
ENV CP_ID=CP_001
ENV CENTRAL_IP=localhost
ENV CENTRAL_PORT=5000
ENV ENGINE_IP=localhost
ENV ENGINE_PORT=5001

# Exponer puerto si es necesario
EXPOSE 5002

CMD ["python", "EV_CP_M.py"]