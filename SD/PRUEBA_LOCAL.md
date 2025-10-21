# 🧪 PRUEBA EN LOCAL (1 SOLO PC)

Esta guía te permite **probar todo el sistema en un solo PC** usando `localhost`.

---

## 🎯 CONFIGURACIÓN RÁPIDA

### 1. Editar network_config.py

Abre `network_config.py` y configura TODO con `localhost`:

```python
# ==== CONFIGURACIÓN DE IPS POR PC ====

PC1_IP = "localhost"  # Driver
PC2_IP = "localhost"  # Central + Kafka
PC3_IP = "localhost"  # Monitor
```

**Guarda el archivo.** ✅

---

### 2. Crear docker-compose.local.yml

Voy a crear un archivo especial que ejecuta **todos los servicios** en un solo PC:

```yaml
version: '3.8'

services:
  # ============================================================================
  # KAFKA BROKER
  # ============================================================================
  kafka-broker:
    image: apache/kafka:latest
    container_name: ev-kafka-broker
    ports:
      - "9092:9092"
      - "29092:29092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka-broker:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka-broker:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://kafka-broker:29092,CONTROLLER://kafka-broker:29093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'ev-charging-cluster-local'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
    volumes:
      - kafka-data:/tmp/kraft-combined-logs
    healthcheck:
      test: ["CMD-SHELL", "kafka-broker-api-versions.sh --bootstrap-server localhost:29092 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  # ============================================================================
  # KAFKA UI
  # ============================================================================
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: ev-kafka-ui
    ports:
      - "8080:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: ev-charging-cluster
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka-broker:29092
      DYNAMIC_CONFIG_ENABLED: 'true'
    depends_on:
      kafka-broker:
        condition: service_healthy
    restart: unless-stopped

  # ============================================================================
  # EV CENTRAL
  # ============================================================================
  ev-central:
    build:
      context: .
      dockerfile: EV_Central/Dockerfile
    container_name: ev-central
    ports:
      - "5000:5000"
      - "8002:8002"
    environment:
      - KAFKA_BROKER=kafka-broker:29092
      - PYTHONUNBUFFERED=1
    volumes:
      - ./ev_charging.db:/app/data/ev_charging.db
      - ./network_config.py:/app/network_config.py
      - ./database.py:/app/database.py
      - ./event_utils.py:/app/event_utils.py
    depends_on:
      kafka-broker:
        condition: service_healthy
    restart: unless-stopped

  # ============================================================================
  # EV DRIVER
  # ============================================================================
  ev-driver:
    build:
      context: .
      dockerfile: EV_Driver/Dockerfile
    container_name: ev-driver
    ports:
      - "8001:8001"
    environment:
      - WS_PORT=8001
      - KAFKA_BROKER=kafka-broker:29092
      - PYTHONUNBUFFERED=1
    volumes:
      - ./ev_charging.db:/app/data/ev_charging.db
      - ./network_config.py:/app/network_config.py
      - ./database.py:/app/database.py
      - ./event_utils.py:/app/event_utils.py
    depends_on:
      kafka-broker:
        condition: service_healthy
    restart: unless-stopped

  # ============================================================================
  # EV MONITOR
  # ============================================================================
  ev-monitor:
    build:
      context: .
      dockerfile: EV_CP_M/Dockerfile
    container_name: ev-monitor
    ports:
      - "8003:8003"
    environment:
      - WS_PORT=8003
      - KAFKA_BROKER=kafka-broker:29092
      - PYTHONUNBUFFERED=1
    volumes:
      - ./ev_charging.db:/app/data/ev_charging.db
      - ./network_config.py:/app/network_config.py
      - ./database.py:/app/database.py
      - ./event_utils.py:/app/event_utils.py
    depends_on:
      kafka-broker:
        condition: service_healthy
    restart: unless-stopped

volumes:
  kafka-data:

# ==============================================================================
# INFORMACIÓN DE USO
# ==============================================================================
# 
# Iniciar:     docker-compose -f docker-compose.local.yml up -d --build
# Ver logs:    docker-compose -f docker-compose.local.yml logs -f
# Detener:     docker-compose -f docker-compose.local.yml down
# 
# Acceso:
# - Kafka UI:      http://localhost:8080
# - Admin:         http://localhost:8002
# - Driver:        http://localhost:8001
# - Monitor:       http://localhost:8003
# 
# ==============================================================================
```

---

## 🚀 PASOS PARA PROBAR

### Paso 1: Inicializar Base de Datos

```powershell
python init_db.py
```

### Paso 2: Iniciar TODO con Docker

```powershell
docker-compose -f docker-compose.local.yml up -d --build
```

**Tiempo:** 3-5 minutos la primera vez.

### Paso 3: Verificar que todo está corriendo

```powershell
docker-compose -f docker-compose.local.yml ps
```

Deberías ver **5 contenedores** en estado "Up":
```
NAME              STATUS
ev-kafka-broker   Up
ev-kafka-ui       Up
ev-central        Up
ev-driver         Up
ev-monitor        Up
```

### Paso 4: Ver logs en tiempo real

```powershell
docker-compose -f docker-compose.local.yml logs -f
```

Presiona `Ctrl+C` para salir.

---

## 🌐 ACCEDER A LAS INTERFACES

Abre tu navegador en:

| Servicio | URL | Descripción |
|----------|-----|-------------|
| **Kafka UI** | http://localhost:8080 | Ver mensajes de Kafka |
| **Admin Dashboard** | http://localhost:8002 | Panel de administración |
| **Driver Dashboard** | http://localhost:8001 | Interfaz de conductor |
| **Monitor Dashboard** | http://localhost:8003 | Monitorización de CPs |

---

## ✅ PROBAR EL FLUJO COMPLETO

### 1. Abrir las 4 ventanas del navegador

```
http://localhost:8001  (Driver)
http://localhost:8002  (Admin)
http://localhost:8003  (Monitor)
http://localhost:8080  (Kafka UI)
```

### 2. En el Dashboard del Driver (localhost:8001)

1. Login con:
   - Usuario: `user1`
   - Contraseña: `pass1`

2. Verás tu saldo: `€150.00`

3. Click en **"Solicitar Carga"**

4. Introduce:
   - kWh deseados: `10`
   - Ubicación: `Alicante-Campus-01`

5. Click **"Enviar Solicitud"**

### 3. En el Dashboard Admin (localhost:8002)

- Deberías ver la solicitud aparecer automáticamente
- Estado: "pending" → "in_progress" → "completed"

### 4. En el Dashboard Monitor (localhost:8003)

- Verás los charging points actualizarse en tiempo real
- Estado cambia según las solicitudes

### 5. En Kafka UI (localhost:8080)

1. Click en tu cluster: `ev-charging-cluster`
2. Click en **"Topics"**
3. Verás 4 topics:
   - `driver-events`
   - `cp-events`
   - `central-events`
   - `monitor-events`

4. Click en cualquier topic → **"Messages"**
5. Verás los mensajes JSON fluyendo en tiempo real

---

## 🛠️ COMANDOS ÚTILES

### Ver logs de un servicio específico

```powershell
# Kafka
docker logs ev-kafka-broker -f

# Central
docker logs ev-central -f

# Driver
docker logs ev-driver -f

# Monitor
docker logs ev-monitor -f
```

### Reiniciar un servicio

```powershell
docker-compose -f docker-compose.local.yml restart ev-driver
```

### Reconstruir después de cambios en código

```powershell
docker-compose -f docker-compose.local.yml down
docker-compose -f docker-compose.local.yml up -d --build
```

### Ver uso de recursos

```powershell
docker stats
```

### Limpiar todo (CUIDADO: borra volúmenes)

```powershell
docker-compose -f docker-compose.local.yml down -v
```

---

## 🐛 TROUBLESHOOTING

### Puerto ocupado

```powershell
# Ver qué proceso usa el puerto
netstat -ano | findstr :8001

# Matar el proceso
taskkill /PID <PID> /F
```

### Kafka no arranca

```powershell
# Ver logs
docker logs ev-kafka-broker

# Reiniciar
docker-compose -f docker-compose.local.yml restart kafka-broker
```

### "Cannot connect to database"

```powershell
# Verificar que ev_charging.db existe
dir ev_charging.db

# Si no existe, reinicializar
python init_db.py
```

### Dashboards muestran error

```powershell
# Verificar que todos los contenedores están corriendo
docker-compose -f docker-compose.local.yml ps

# Ver logs para errores
docker-compose -f docker-compose.local.yml logs
```

---

## 🔄 WORKFLOW DE DESARROLLO

Cuando hagas cambios en el código:

```powershell
# 1. Detener
docker-compose -f docker-compose.local.yml down

# 2. Hacer cambios en tu código

# 3. Reconstruir e iniciar
docker-compose -f docker-compose.local.yml up -d --build

# 4. Ver logs
docker-compose -f docker-compose.local.yml logs -f
```

---

## 📊 VERIFICAR QUE KAFKA FUNCIONA

### Desde terminal (dentro del contenedor):

```powershell
# Listar topics
docker exec ev-kafka-broker kafka-topics.sh --bootstrap-server localhost:29092 --list

# Ver mensajes de un topic
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events --from-beginning
```

---

## 🎉 ¡LISTO!

Si todo funciona en local, el sistema está listo para **desplegarse en 3 PCs**.

Solo necesitas:
1. Cambiar `localhost` por las IPs reales en `network_config.py`
2. Usar `docker-compose.pc1.yml`, `pc2.yml`, `pc3.yml` en cada PC

---

**¿Problemas?** Revisa los logs con `docker-compose logs -f` 🔍
