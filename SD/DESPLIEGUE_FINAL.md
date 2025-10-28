# 📋 Despliegue Final - Central + Driver en PCs Separados

## 🔍 Problema Detectado

El Driver envía una solicitud de autorización, el Central asigna un CP y lo marca como "reserved", pero el CP **NO pasa a "charging"** porque el evento `charging_started` no llega al Central.

## 📊 Flujo Completo Esperado

```
1. [Driver] Envía AUTHORIZATION_REQUEST → Kafka
2. [Central] Recibe, asigna CP automáticamente, marca CP como "reserved"
3. [Central] Envía AUTHORIZATION_RESPONSE → Kafka  
4. [Driver] Recibe autorización
5. [Driver] Envía charging_started → Kafka ❌ <-- AQUÍ FALLA
6. [Central] Recibe charging_started y cambia CP de "reserved" → "charging"
```

## ✅ Solución

### 1. Verificar que el Producer del Driver funcione

En el PC del Driver:

```powershell
docker logs ev-driver -f
```

Busca:
```
✅ [DRIVER] ✅ Kafka producer and consumer initialized
```

Si NO ves esto, el producer NO está funcionando.

### 2. Verificar conectividad a Kafka

Desde el PC del Driver:

```powershell
# Probar conexión TCP a Kafka
Test-NetConnection -ComputerName 172.20.10.8 -Port 9092

# Probar desde dentro del contenedor
docker exec ev-driver ping 172.20.10.8
```

### 3. Verificar que el Consumer del Central esté escuchando

En el PC del Central (este PC):

```powershell
docker logs ev-central -f | Select-String "📨 Received|charging_started"
```

Cuando el Driver envíe `charging_started`, DEBERÍAS ver:
```
[CENTRAL] 📨 Received event: charging_started
[CENTRAL] ⚡ Suministro iniciado - Sesión X en CP Y
```

### 4. Si NO ves el evento, el problema es de conectividad

**Opciones:**

A) **Network Mode Host** (mejor para Docker Desktop en Windows):
```yaml
# En docker-compose.pc1.yml
services:
  ev-driver:
    network_mode: "host"  # Esto permite que el contenedor acceda a la red del host
```

B) **Usar IP del host Docker**:
Si Docker usa una red virtual (Docker Desktop), el contenedor no puede alcanzar 172.20.10.8.
En ese caso, dentro del contenedor debes usar la IP del host Docker.

Para encontrar la IP del host Docker desde dentro del contenedor:
```powershell
# Dentro del contenedor
docker exec ev-driver ip route | Select-String "default"
# O
docker exec ev-driver cat /etc/resolv.conf
```

C) **Usar "host.docker.internal"** (Windows Docker Desktop):
```yaml
environment:
  KAFKA_BROKER: host.docker.internal:9092  # Para Windows Docker Desktop
```

## 🔧 Configuración Final

### En PC2 (Central - Este PC)

Ya está corriendo:
- Kafka: `172.20.10.8:9092`
- Central: Puerto 8002

### En PC1 (Driver - Otro PC)

Editar `SD/docker-compose.pc1.yml`:

```yaml
services:
  ev-driver:
    build:
      context: .
      dockerfile: EV_Driver/Dockerfile
    container_name: ev-driver
    network_mode: "host"  # ← CAMBIO AQUÍ
    # ports:           # ← COMENTAR ESTAS LÍNEAS
    #   - "8001:8001"
    environment:
      KAFKA_BROKER: 172.20.10.8:9092  # IP del Central
      CENTRAL_IP: 172.20.10.8
      WS_PORT: 8001
      PYTHONUNBUFFERED: 1
    volumes:
      - ./ev_charging.db:/app/ev_charging.db
      - ./network_config.py:/app/network_config.py
      - ./database.py:/app/database.py
      - ./event_utils.py:/app/event_utils.py
      - ./EV_Driver/dashboard.html:/app/dashboard.html
    restart: unless-stopped
```

**NOTA**: `network_mode: "host"` **NO FUNCIONA en Windows Docker Desktop**.

### Alternativa para Windows: Usar IP del Gateway de Docker

Si estás en Windows y `network_mode: "host"` no funciona:

1. Encontrar la IP del gateway Docker:
```powershell
docker network inspect bridge | Select-String "Gateway"
```

2. Actualizar `docker-compose.pc1.yml` con esa IP

### O usa Python directamente (SIN Docker) en el Driver

```powershell
# En el PC del Driver
cd SD
python EV_Driver/EV_Driver_WebSocket.py
```

Esto evita problemas de red de Docker.

## 🧪 Test del Flujo Completo

1. **Desde el Driver**: Solicita carga
2. **En los logs del Central**:
   ```powershell
   docker logs ev-central -f
   ```
   
   Deberías ver:
   ```
   [CENTRAL] 🔐 Solicitud de autorización: usuario=driver1, buscando CP disponible...
   [CENTRAL] 🎯 CP CP_001 asignado y reservado automáticamente para driver1
   [CENTRAL] 📨 Received event: charging_started from topic: driver-events
   [CENTRAL] ⚡ Suministro iniciado - Sesión X en CP CP_001 para usuario driver1
   ```

3. **Verificar BD**:
   ```powershell
   python database.py
   # Opción 2: Ver todos los puntos de carga
   ```

   El CP debería estar en estado **"charging"**, NO "reserved".

## 🐛 Si el problema persiste

Comparte:
1. Logs del Driver: `docker logs ev-driver`
2. Logs del Central: `docker logs ev-central`
3. Output de: `Test-NetConnection -ComputerName 172.20.10.8 -Port 9092`


