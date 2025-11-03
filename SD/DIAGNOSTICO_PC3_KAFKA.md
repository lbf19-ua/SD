# 🔍 Diagnóstico: PC3 no se conecta a Kafka en PC2

## Pasos de Diagnóstico Rápido

### Paso 1: Verificar archivo `.env` en PC3
```bash
# En PC3, ejecutar:
cat .env

# Debe mostrar (SIN comillas):
PC2_IP=192.168.1.XXX
KAFKA_BROKER=192.168.1.XXX:9092
KAFKA_PORT=9092
```

**❌ Si muestra comillas, corregir:**
```bash
# INCORRECTO:
KAFKA_BROKER="192.168.1.100:9092"

# CORRECTO:
KAFKA_BROKER=192.168.1.100:9092
```

### Paso 2: Verificar archivo `.env` en PC2
```bash
# En PC2, ejecutar:
cat .env

# Debe mostrar (SIN comillas):
PC2_IP=192.168.1.XXX  # IP real de PC2
KAFKA_BROKER=broker:29092
KAFKA_PORT=9092
```

**⚠️ IMPORTANTE:** La IP en `PC2_IP` de PC2 debe ser **exactamente la misma** que la IP en `KAFKA_BROKER` de PC3.

### Paso 3: Verificar conectividad de red
```powershell
# En PC3, ejecutar (reemplazar con IP real de PC2):
Test-NetConnection -ComputerName 192.168.1.XXX -Port 9092

# Debe mostrar:
# TcpTestSucceeded : True
```

**❌ Si muestra `TcpTestSucceeded : False`:**
- Firewall en PC2 bloqueando puerto 9092
- Kafka no está corriendo en PC2
- IP incorrecta

### Paso 4: Verificar que Kafka está corriendo en PC2
```bash
# En PC2, ejecutar:
docker ps | grep kafka

# Debe mostrar:
# ev-kafka-broker    Up   ...  0.0.0.0:9092->9092/tcp
```

**❌ Si no está corriendo:**
```bash
docker-compose -f docker-compose.pc2.yml up -d kafka-broker
```

### Paso 5: Verificar configuración de listeners en Kafka
```bash
# En PC2, ejecutar:
docker logs ev-kafka-broker 2>&1 | grep -i listener

# Debe mostrar que PLAINTEXT_HOST está escuchando en 0.0.0.0:9092
```

### Paso 6: Verificar logs del Engine en PC3
```bash
# En PC3, ejecutar:
docker logs ev-cp-engine-001 2>&1 | grep -iE "(kafka|error|failed|connect)"

# Buscar:
# - ✅ "Kafka connected successfully"
# - ❌ "Failed to connect"
# - ❌ "Connection refused"
# - ❌ "NoBrokersAvailable"
```

### Paso 7: Verificar variables de entorno en contenedores
```bash
# En PC3, ejecutar:
docker exec ev-cp-engine-001 env | grep KAFKA_BROKER

# Debe mostrar:
# KAFKA_BROKER=192.168.1.XXX:9092  (SIN comillas)
```

**❌ Si muestra comillas o está vacío:**
- El `.env` tiene comillas o formato incorrecto
- Reconstruir contenedores: `docker-compose -f docker-compose.pc3.yml up -d --build`

## 🔧 Soluciones Comunes

### Problema 1: Variables con comillas en `.env`
**Síntoma:** IP aparece con comillas en logs o variables de entorno

**Solución:**
1. Editar `.env` en PC3
2. Eliminar todas las comillas
3. Guardar archivo
4. Reiniciar contenedores: `docker-compose -f docker-compose.pc3.yml restart`

### Problema 2: IPs no coinciden entre PC2 y PC3
**Síntoma:** `KAFKA_ADVERTISED_LISTENERS` muestra IP diferente a la que usa PC3

**Solución:**
1. En PC2, obtener IP real: `ipconfig | findstr IPv4`
2. Actualizar `.env` en PC2: `PC2_IP=<IP_REAL>`
3. Actualizar `.env` en PC3: `KAFKA_BROKER=<IP_REAL>:9092`
4. Reiniciar Kafka en PC2: `docker-compose -f docker-compose.pc2.yml restart kafka-broker`
5. Reiniciar contenedores en PC3: `docker-compose -f docker-compose.pc3.yml restart`

### Problema 3: Firewall bloqueando conexión
**Síntoma:** `Test-NetConnection` falla desde PC3

**Solución:**
```powershell
# En PC2 (PowerShell como admin):
New-NetFirewallRule -DisplayName "EV Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
```

### Problema 4: Kafka no reinició después de cambiar `.env`
**Síntoma:** Cambiaste `.env` pero Kafka sigue usando configuración antigua

**Solución:**
```bash
# En PC2:
docker-compose -f docker-compose.pc2.yml down
docker-compose -f docker-compose.pc2.yml up -d
```

### Problema 5: Error de configuración de timeout
**Síntoma:** `KafkaConfigurationError: request timeout must be larger than session timeout`

**Solución:**
✅ **YA CORREGIDO** en el código. Si persiste:
```bash
# En PC3, reconstruir contenedores:
docker-compose -f docker-compose.pc3.yml down
docker-compose -f docker-compose.pc3.yml build --no-cache
docker-compose -f docker-compose.pc3.yml up -d
```

## 📋 Script de Diagnóstico Automático

Ejecutar en PC3:
```bash
python diagnostic_kafka_connection.py
```

Este script verifica:
- ✅ Existencia y formato de `.env`
- ✅ Variables sin comillas
- ✅ Formato correcto de `KAFKA_BROKER`
- ✅ Conexión real a Kafka

## 🆘 Si Nada Funciona

1. **Verificar logs completos:**
   ```bash
   # En PC3:
   docker logs ev-cp-engine-001 --tail 100
   docker logs ev-cp-monitor-001 --tail 100
   
   # En PC2:
   docker logs ev-kafka-broker --tail 100
   ```

2. **Reconstruir todo desde cero:**
   ```bash
   # En PC2:
   docker-compose -f docker-compose.pc2.yml down
   docker-compose -f docker-compose.pc2.yml up -d --build
   
   # En PC3:
   docker-compose -f docker-compose.pc3.yml down
   docker-compose -f docker-compose.pc3.yml up -d --build
   ```

3. **Verificar red compartida:**
   - PC2 y PC3 deben estar en la misma red local
   - Probar ping: `ping <IP_PC2>` desde PC3


