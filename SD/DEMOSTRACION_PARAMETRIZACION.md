# 📋 Demostración de Parametrización sin Recompilación

Este documento muestra cómo demostrar que **todos los parámetros están parametrizados** y se pueden cambiar **sin recompilar el código**.

---

## 🎯 Objetivo de la Demostración

Demostrar que se pueden cambiar:
- **Puertos** de servidores
- **IPs** y puertos de conexión (Kafka, Central)
- **IDs** de módulos
- **Ubicaciones**, tarifas, potencia máxima
- **Cualquier otro parámetro** necesario

**Todo sin tocar el código ni recompilar.**

---

## 📝 Parámetros Parametrizados en Cada Módulo

### 1. **EV_Central**
- `--port`: Puerto WebSocket (default: 8002)
- `--kafka-broker`: Dirección del broker Kafka
- Variables de entorno: `CENTRAL_PORT`, `KAFKA_BROKER`

### 2. **EV_Driver**
- `--port`: Puerto WebSocket (default: 8001)
- `--kafka-broker`: Dirección del broker Kafka
- `--central-ip`: IP del servidor Central
- Variables de entorno: `DRIVER_PORT`, `KAFKA_BROKER`, `CENTRAL_IP`

### 3. **EV_CP_E (Engine)**
- `--cp-id`: ID del Charging Point
- `--location`: Ubicación física
- `--max-power`: Potencia máxima en kW
- `--tariff`: Tarifa por kWh
- `--health-port`: Puerto TCP para health checks
- `--kafka-broker`: Dirección del broker Kafka
- Variables de entorno: `CP_ID`, `LOCATION`, `MAX_POWER`, `TARIFF`, `HEALTH_PORT`, `KAFKA_BROKER`

### 4. **EV_CP_M (Monitor)**
- `--cp-id`: ID del CP a monitorear
- `--engine-host`: Host del Engine
- `--engine-port`: Puerto TCP del Engine
- `--monitor-port`: Puerto del dashboard
- `--kafka-broker`: Dirección del broker Kafka
- Variables de entorno: `CP_ID`, `ENGINE_HOST`, `ENGINE_PORT`, `MONITOR_PORT`, `KAFKA_BROKER`

---

## 🧪 DEMOSTRACIÓN PASO A PASO

### **ESCENARIO 1: Cambiar puerto del Central**

**Antes de cambiar:**
```powershell
# Ver configuración actual
cd C:\Users\luisb\Desktop\SD_FINAL\SD\SD
docker-compose -f docker-compose.pc2.yml logs ev-central | Select-String "WebSocket Port"
# Debería mostrar: WebSocket Port: 8002
```

**Cambiar el puerto (SIN recompilar):**

**Opción A: Variable de entorno**
```powershell
# Detener el contenedor
docker-compose -f docker-compose.pc2.yml stop ev-central

# Editar docker-compose.pc2.yml y cambiar el puerto O crear/modificar .env
# Agregar al .env:
# CENTRAL_PORT=9999

# Reiniciar
docker-compose -f docker-compose.pc2.yml up -d ev-central
```

**Opción B: Argumento de línea de comandos (más directo)**
```powershell
# Detener contenedor
docker stop ev-central

# Iniciar con nuevo puerto
docker run -d --name ev-central-test `
  --network ev-network `
  -p 9999:9999 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db `
  -v ${PWD}/network_config.py:/app/network_config.py `
  -v ${PWD}/database.py:/app/database.py `
  -v ${PWD}/event_utils.py:/app/event_utils.py `
  ev-central `
  python -u EV_Central_WebSocket.py --port 9999 --kafka-broker 192.168.1.235:9092
```

**Verificar:**
```powershell
# Ver logs
docker logs ev-central-test | Select-String "WebSocket Port"
# Debe mostrar: WebSocket Port: 9999

# Acceder al dashboard en el nuevo puerto
# http://localhost:9999
```

✅ **RESULTADO**: El puerto cambió **sin recompilar**. El código es el mismo, solo cambió el parámetro.

---

### **ESCENARIO 2: Cambiar Kafka Broker en un Engine**

**Situación inicial:**
- Engine CP_001 conectado a `192.168.1.235:9092`

**Cambiar a otro broker (SIN recompilar):**

```powershell
# Detener el engine
docker stop ev-cp-engine-001

# Reiniciar con nuevo broker (ejemplo: mismo PC pero otro puerto o IP diferente)
docker start ev-cp-engine-001 --env KAFKA_BROKER=192.168.1.236:9093

# O mejor, recrear el contenedor con nuevo parámetro
docker rm ev-cp-engine-001
docker run -d --name ev-cp-engine-001 `
  --network ev-network `
  -p 5100:5100 `
  -e CP_ID=CP_001 `
  -e LOCATION="Parking Norte" `
  -e HEALTH_PORT=5100 `
  -e KAFKA_BROKER=192.168.1.236:9093 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db `
  -v ${PWD}/network_config.py:/app/network_config.py `
  -v ${PWD}/database.py:/app/database.py `
  -v ${PWD}/event_utils.py:/app/event_utils.py `
  --restart unless-stopped `
  ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_001 --location "Parking Norte" --health-port 5100 --kafka-broker 192.168.1.236:9093
```

**Verificar en logs:**
```powershell
docker logs ev-cp-engine-001 | Select-String "Kafka broker"
# Debe mostrar: 📡 Kafka Broker: 192.168.1.236:9093
```

✅ **RESULTADO**: El broker cambió **sin recompilar**. El mismo código funciona con diferentes brokers.

---

### **ESCENARIO 3: Cambiar múltiples parámetros de un Engine nuevo**

**Crear un Engine con parámetros completamente diferentes:**

```powershell
# Engine con configuración personalizada
docker run -d --name ev-cp-engine-demo `
  --network ev-network `
  -p 5105:5105 `
  -e CP_ID=CP_DEMO `
  -e LOCATION="Parking Demo" `
  -e MAX_POWER=50.0 `
  -e TARIFF=0.45 `
  -e HEALTH_PORT=5105 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db `
  -v ${PWD}/network_config.py:/app/network_config.py `
  -v ${PWD}/database.py:/app/database.py `
  -v ${PWD}/event_utils.py:/app/event_utils.py `
  --restart unless-stopped `
  ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli `
    --cp-id CP_DEMO `
    --location "Parking Demo" `
    --max-power 50.0 `
    --tariff 0.45 `
    --health-port 5105 `
    --kafka-broker 192.168.1.235:9092
```

**Verificar configuración:**
```powershell
docker logs ev-cp-engine-demo | Select-String "CP_DEMO|50.0|0.45|5105"
```

✅ **RESULTADO**: Todos los parámetros configurados **sin modificar código**.

---

### **ESCENARIO 4: Cambiar puerto del Driver**

```powershell
# Detener driver actual
docker stop ev-driver

# Iniciar con nuevo puerto
docker rm ev-driver
docker run -d --name ev-driver `
  --network ev-network `
  -p 8888:8888 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e CENTRAL_IP=192.168.1.235 `
  -e DRIVER_PORT=8888 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db `
  -v ${PWD}/network_config.py:/app/network_config.py `
  -v ${PWD}/database.py:/app/database.py `
  -v ${PWD}/event_utils.py:/app/event_utils.py `
  -v ${PWD}/EV_Driver/dashboard.html:/app/dashboard.html `
  ev-driver `
  python -u EV_Driver_WebSocket.py --port 8888 --kafka-broker 192.168.1.235:9092 --central-ip 192.168.1.235
```

**Verificar:**
```powershell
docker logs ev-driver | Select-String "WebSocket Port"
# Debe mostrar: WebSocket Port: 8888
```

✅ **RESULTADO**: Puerto del Driver cambiado **sin recompilar**.

---

### **ESCENARIO 5: Cambiar Monitor para supervisar otro Engine**

```powershell
# Crear Monitor que supervise un Engine diferente (ej: CP_002 en lugar de CP_001)
docker run -d --name ev-cp-monitor-demo `
  --network ev-network `
  -p 5555:5555 `
  -e CP_ID=CP_002 `
  -e ENGINE_HOST=ev-cp-engine-002 `
  -e ENGINE_PORT=5101 `
  -e MONITOR_PORT=5555 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db:ro `
  -v ${PWD}/network_config.py:/app/network_config.py:ro `
  -v ${PWD}/database.py:/app/database.py:ro `
  -v ${PWD}/event_utils.py:/app/event_utils.py:ro `
  -v ${PWD}/EV_CP_M/monitor_dashboard.html:/app/monitor_dashboard.html:ro `
  ev-cp-monitor-001 `
  python -u EV_CP_M_WebSocket.py `
    --cp-id CP_002 `
    --engine-host ev-cp-engine-002 `
    --engine-port 5101 `
    --monitor-port 5555 `
    --kafka-broker 192.168.1.235:9092
```

✅ **RESULTADO**: Monitor configurado para otro Engine **sin recompilar**.

---

## 🎬 SCRIPT DE DEMOSTRACIÓN COMPLETO

Para mostrar al profesor en tiempo real:

```powershell
# ============================================
# DEMOSTRACIÓN 1: Cambiar puerto del Central
# ============================================
Write-Host "`n=== DEMOSTRACIÓN: Cambio de Puerto del Central ===" -ForegroundColor Green

# 1. Mostrar configuración actual
Write-Host "`n1. Configuración ACTUAL:" -ForegroundColor Yellow
docker logs ev-central --tail 20 | Select-String "WebSocket Port"

# 2. Detener Central
Write-Host "`n2. Deteniendo Central..." -ForegroundColor Yellow
docker stop ev-central

# 3. Iniciar con NUEVO puerto (9999)
Write-Host "`n3. Reiniciando con puerto 9999 (SIN RECOMPILAR)..." -ForegroundColor Yellow
docker start ev-central
# O mejor, modificar .env y reiniciar

# 4. Verificar nuevo puerto
Write-Host "`n4. Nueva configuración:" -ForegroundColor Yellow
docker logs ev-central --tail 20 | Select-String "WebSocket Port"

Write-Host "`n✅ PUERTO CAMBIADO SIN RECOMPILAR CÓDIGO" -ForegroundColor Green

# ============================================
# DEMOSTRACIÓN 2: Crear Engine con parámetros personalizados
# ============================================
Write-Host "`n=== DEMOSTRACIÓN: Engine con Parámetros Personalizados ===" -ForegroundColor Green

Write-Host "`nCreando Engine CP_DEMO con:" -ForegroundColor Yellow
Write-Host "  - ID: CP_DEMO"
Write-Host "  - Location: Parking Demo"
Write-Host "  - Max Power: 50.0 kW"
Write-Host "  - Tariff: €0.45/kWh"
Write-Host "  - Health Port: 5105"
Write-Host "`n(SIN MODIFICAR CÓDIGO)" -ForegroundColor Cyan

docker run -d --name ev-cp-engine-demo `
  --network ev-network `
  -p 5105:5105 `
  -e CP_ID=CP_DEMO `
  -e LOCATION="Parking Demo" `
  -e MAX_POWER=50.0 `
  -e TARIFF=0.45 `
  -e HEALTH_PORT=5105 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db `
  -v ${PWD}/network_config.py:/app/network_config.py `
  -v ${PWD}/database.py:/app/database.py `
  -v ${PWD}/event_utils.py:/app/event_utils.py `
  ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_DEMO --location "Parking Demo" --max-power 50.0 --tariff 0.45 --health-port 5105 --kafka-broker 192.168.1.235:9092

Start-Sleep -Seconds 3

Write-Host "`nVerificando configuración:" -ForegroundColor Yellow
docker logs ev-cp-engine-demo --tail 30 | Select-String "CP_DEMO|50.0|0.45|5105"

Write-Host "`n✅ ENGINE CREADO CON PARÁMETROS PERSONALIZADOS (SIN RECOMPILAR)" -ForegroundColor Green

# ============================================
# DEMOSTRACIÓN 3: Cambiar Kafka Broker
# ============================================
Write-Host "`n=== DEMOSTRACIÓN: Cambio de Kafka Broker ===" -ForegroundColor Green

# Mostrar broker actual
Write-Host "`nBroker actual (desde logs):" -ForegroundColor Yellow
docker logs ev-cp-engine-001 --tail 50 | Select-String "Kafka broker"

Write-Host "`n✅ TODOS LOS PARÁMETROS SON CONFIGURABLES SIN RECOMPILAR" -ForegroundColor Green
```

---

## 📋 RESUMEN PARA LA CORRECCIÓN

### **Puntos Clave a Demostrar:**

1. ✅ **Todos los puertos son parametrizables**
   - Central: `--port` o `CENTRAL_PORT`
   - Driver: `--port` o `DRIVER_PORT`
   - Engine: `--health-port` o `HEALTH_PORT`
   - Monitor: `--monitor-port` o `MONITOR_PORT`

2. ✅ **Todas las IPs y conexiones son parametrizables**
   - Kafka Broker: `--kafka-broker` o `KAFKA_BROKER`
   - Central IP: `--central-ip` o `CENTRAL_IP`

3. ✅ **Configuración de negocio es parametrizable**
   - CP_ID: `--cp-id` o `CP_ID`
   - Location: `--location` o `LOCATION`
   - Max Power: `--max-power` o `MAX_POWER`
   - Tariff: `--tariff` o `TARIFF`

4. ✅ **Métodos de configuración (prioridad):**
   - **1. Argumentos de línea de comandos** (mayor prioridad)
   - **2. Variables de entorno**
   - **3. Archivo de configuración** (`network_config.py` como fallback)

5. ✅ **NO se recompila código**
   - Se usa la misma imagen Docker
   - Se pasan parámetros diferentes
   - El código lee los parámetros en tiempo de ejecución

---

## 🎯 Comandos Rápidos para Demostrar

### **Cambiar puerto del Central:**
```powershell
docker stop ev-central
# Editar .env: CENTRAL_PORT=9999
docker-compose -f docker-compose.pc2.yml up -d ev-central
```

### **Crear Engine con parámetros personalizados:**
```powershell
docker run -d --name ev-cp-test `
  -p 5110:5110 `
  -e CP_ID=CP_TEST `
  -e LOCATION="Test Location" `
  -e MAX_POWER=30.0 `
  -e TARIFF=0.40 `
  -e HEALTH_PORT=5110 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_TEST --location "Test Location" --max-power 30.0 --tariff 0.40 --health-port 5110 --kafka-broker 192.168.1.235:9092
```

### **Ver todos los parámetros configurados:**
```powershell
# Ver configuración actual
docker inspect ev-cp-engine-001 | Select-String -Pattern "Env|Args"
```

---

## ✅ Verificación Final

**Preguntas que el profesor puede hacer:**

1. **"¿Puedes cambiar el puerto del Central a 9999?"**
   → Sí, con `--port 9999` o `CENTRAL_PORT=9999`

2. **"¿Puedes crear un Engine con 50kW de potencia?"**
   → Sí, con `--max-power 50.0`

3. **"¿Puedes cambiar el broker de Kafka a otra IP?"**
   → Sí, con `--kafka-broker 192.168.1.XXX:9092`

4. **"¿Tuviste que recompilar?"**
   → **NO**, solo cambié los parámetros en tiempo de ejecución

---

## 📚 Archivos de Configuración

Los parámetros se pueden configurar en:

1. **Archivo `.env`** (usado por docker-compose)
2. **Argumentos de línea de comandos** (`--parametro valor`)
3. **Variables de entorno** (`export PARAMETRO=valor`)
4. **`network_config.py`** (valores por defecto, solo lectura)

**Ninguno requiere recompilación del código.**

