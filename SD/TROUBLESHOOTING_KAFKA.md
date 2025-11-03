# 🔧 Troubleshooting: Conexión Kafka entre PC2 y PC3

## Problema: No hay comunicación entre PC2 (Kafka) y PC3 (Engine/Monitor)

### ✅ Checklist de Verificación

#### 1. Verificar archivo `.env` en PC2
```bash
# En PC2, verificar que existe .env con:
cat .env

# Debe contener:
PC2_IP=192.168.1.XXX  # IP real de PC2
KAFKA_BROKER=broker:29092
KAFKA_PORT=9092
```

#### 2. Verificar archivo `.env` en PC3
```bash
# En PC3, verificar que existe .env con:
cat .env

# Debe contener:
PC2_IP=192.168.1.XXX  # IP real de PC2 (la misma que en PC2)
KAFKA_BROKER=192.168.1.XXX:9092  # IP_PC2:9092
KAFKA_PORT=9092
```

#### 3. Verificar que Kafka está escuchando en 0.0.0.0:9092
```bash
# En PC2, verificar configuración de Kafka:
docker logs ev-kafka-broker | grep LISTENER

# Debe mostrar:
# PLAINTEXT_HOST listener en 0.0.0.0:9092
```

#### 4. Verificar conectividad de red desde PC3 a PC2
```powershell
# En PC3, probar conectividad:
Test-NetConnection -ComputerName <IP_PC2> -Port 9092

# O con telnet (si está instalado):
telnet <IP_PC2> 9092
```

#### 5. Verificar firewall en PC2
```powershell
# En PC2 (PowerShell como admin):
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*EV*"}

# Si no existe la regla, crear:
New-NetFirewallRule -DisplayName "EV Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
```

#### 6. Verificar logs de Engine en PC3
```bash
# En PC3:
docker logs ev-cp-engine-001 | grep -i kafka

# Debe mostrar:
# ✅ Kafka connected successfully
# 📡 Listening to: central-events
# 📤 Publishing to: cp-events
```

#### 7. Verificar logs de Monitor en PC3
```bash
# En PC3:
docker logs ev-cp-monitor-001 | grep -i kafka

# Debe mostrar:
# ✅ Kafka producer initialized and connected
# ✅ Consumer connected, listening to [...]
```

#### 8. Verificar logs de Kafka en PC2
```bash
# En PC2:
docker logs ev-kafka-broker | tail -50

# Buscar errores de conexión o problemas de listener
```

### 🔍 Diagnóstico Avanzado

#### Probar conexión manual a Kafka desde PC3
```bash
# Desde PC3, usando kafka-python (si está instalado):
python -c "
from kafka import KafkaProducer
import json
producer = KafkaProducer(
    bootstrap_servers='192.168.1.XXX:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
producer.send('test-topic', {'test': 'message'})
producer.flush()
print('✅ Connection successful')
"
```

#### Verificar que los topics existen
```bash
# En PC2 (desde Kafka UI):
# Acceder a http://<IP_PC2>:8080
# Verificar que existen los topics:
# - driver-events
# - cp-events
# - central-events
# - monitor-events
```

### ⚠️ Errores Comunes

#### Error: "Connection refused" / "ConnectionError"
- **Síntomas**: `kafka.errors.KafkaTimeoutError` o `Connection refused`
- **Causas posibles**:
  1. Firewall bloqueando puerto 9092 en PC2
  2. Kafka no está corriendo en PC2
  3. IP incorrecta en `.env` de PC3
  4. Puerto incorrecto (ej: usando 29092 en lugar de 9092 desde PC3)
- **Soluciones**:
  1. Verificar que Kafka está corriendo: `docker ps | grep kafka`
  2. Verificar firewall en PC2 (ver sección 5 arriba)
  3. Probar conectividad desde PC3: `Test-NetConnection -ComputerName <IP_PC2> -Port 9092`
  4. Verificar `.env` de PC3: `KAFKA_BROKER` debe ser `IP_PC2:9092` (SIN comillas)

#### Error: "Broker not available" / "NoBrokersAvailable"
- **Síntomas**: `kafka.errors.NoBrokersAvailable` o `Broker not available`
- **Causas posibles**:
  1. IP incorrecta en `.env` de PC3
  2. Kafka no está escuchando en `0.0.0.0:9092` (listener incorrecto)
  3. `KAFKA_ADVERTISED_LISTENERS` incorrecto en PC2
  4. Variable `PC2_IP` en `.env` de PC2 vacía o incorrecta
- **Soluciones**:
  1. Verificar `.env` en PC3: `cat .env` - debe mostrar `KAFKA_BROKER=192.168.1.XXX:9092` (sin comillas)
  2. Verificar `.env` en PC2: `cat .env` - debe mostrar `PC2_IP=192.168.1.XXX` (sin comillas, IP real)
  3. Verificar configuración Kafka: `docker logs ev-kafka-broker | grep LISTENER`
  4. Reiniciar Kafka en PC2: `docker-compose -f docker-compose.pc2.yml restart kafka-broker`

#### Error: "No metadata available" / "KafkaTimeoutError"
- **Síntomas**: `kafka.errors.KafkaTimeoutError` o `No metadata available`
- **Causas posibles**:
  1. `KAFKA_ADVERTISED_LISTENERS` incorrecto en PC2 (IP no coincide)
  2. Cliente intentando conectarse usando IP que no está en `KAFKA_ADVERTISED_LISTENERS`
  3. Kafka usa listener interno (`broker:29092`) en lugar de externo (`IP_PC2:9092`)
- **Soluciones**:
  1. Verificar que `PC2_IP` en `.env` de PC2 es la IP real: `ipconfig | findstr IPv4`
  2. Verificar que `KAFKA_ADVERTISED_LISTENERS` incluye `PLAINTEXT_HOST://${PC2_IP}:9092`
  3. En PC3, usar `IP_PC2:9092` (no `broker:29092`)
  4. Reiniciar Kafka después de cambiar `.env`: `docker-compose -f docker-compose.pc2.yml restart`

#### Error: Variables con comillas en `.env`
- **Síntomas**: IP aparece con comillas en los logs: `"192.168.1.100"` en lugar de `192.168.1.100`
- **Causa**: Comillas dobles en archivo `.env` (ej: `KAFKA_BROKER="192.168.1.100:9092"`)
- **Solución**: 
  - Eliminar comillas del `.env`: `KAFKA_BROKER=192.168.1.100:9092` (sin comillas)
  - Verificar: `cat .env` no debe mostrar comillas alrededor de los valores

#### Error: "Request timed out" / "TimeoutError"
- **Síntomas**: `kafka.errors.KafkaTimeoutError` o timeouts después de varios intentos
- **Causas posibles**:
  1. Red lenta o latencia alta entre PC2 y PC3
  2. Firewall bloqueando parcialmente (permite conexión inicial pero bloquea datos)
  3. Kafka sobrecargado o lento
- **Soluciones**:
  1. Aumentar timeout en código (ya configurado a 10 segundos)
  2. Verificar latencia de red: `ping <IP_PC2>`
  3. Verificar logs de Kafka para sobrecarga: `docker logs ev-kafka-broker | tail -100`

#### Error: "KafkaConfigurationError: request timeout 10000 must be larger than session timeout 10000"
- **Síntomas**: Error al inicializar KafkaConsumer o KafkaProducer
- **Causa**: `request_timeout_ms` debe ser mayor que `session_timeout_ms` (por defecto 10s)
- **Solución**: 
  - ✅ **YA CORREGIDO** en el código: `request_timeout_ms` ahora es 30000ms (30s)
  - Si ves este error después de la corrección, reinicia los contenedores:
    ```bash
    # En PC3:
    docker-compose -f docker-compose.pc3.yml restart
    ```

#### Error: "Failed to connect to Kafka after X attempts"
- **Síntomas**: Múltiples intentos fallidos al conectar
- **Causa**: Combinación de problemas anteriores
- **Soluciones**:
  1. Revisar todos los pasos del checklist arriba
  2. Verificar logs detallados en Engine/Monitor para ver el error específico
  3. Probar conexión manual desde PC3 usando el script de diagnóstico avanzado

### 🔍 Verificación Rápida de Errores

#### Comando para verificar errores específicos en logs
```bash
# En PC3, buscar errores de conexión:
docker logs ev-cp-engine-001 2>&1 | grep -iE "(error|failed|refused|timeout|broker)"

# En PC3, buscar errores del Monitor:
docker logs ev-cp-monitor-001 2>&1 | grep -iE "(error|failed|refused|timeout|broker)"

# En PC2, ver errores de Kafka:
docker logs ev-kafka-broker 2>&1 | grep -iE "(error|exception|failed)"
```

#### Verificar formato del archivo `.env`
```bash
# En PC2 o PC3, verificar que .env no tiene comillas:
cat .env | grep -E "PC2_IP|KAFKA_BROKER"

# Debe mostrar (SIN comillas):
# PC2_IP=192.168.1.100
# KAFKA_BROKER=192.168.1.100:9092

# Si muestra con comillas (INCORRECTO):
# PC2_IP="192.168.1.100"  ❌
# KAFKA_BROKER="192.168.1.100:9092"  ❌
```

#### Verificar que las variables se pasan correctamente a contenedores
```bash
# En PC3, verificar variables de entorno del contenedor:
docker exec ev-cp-engine-001 env | grep KAFKA_BROKER

# Debe mostrar:
# KAFKA_BROKER=192.168.1.100:9092

# Si muestra comillas o está vacío, hay problema con el .env
```

### 📝 Comandos Útiles

```bash
# Reiniciar todos los servicios en PC2:
docker-compose -f docker-compose.pc2.yml restart

# Reiniciar todos los servicios en PC3:
docker-compose -f docker-compose.pc3.yml restart

# Ver estado de todos los contenedores:
docker ps -a

# Ver logs en tiempo real:
docker logs -f ev-cp-engine-001
docker logs -f ev-cp-monitor-001
docker logs -f ev-kafka-broker
```

