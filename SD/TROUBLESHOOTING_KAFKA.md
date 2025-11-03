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

#### Error: "Connection refused"
- **Causa**: Firewall bloqueando puerto 9092 o Kafka no está corriendo
- **Solución**: Verificar firewall y estado de Kafka

#### Error: "Broker not available"
- **Causa**: IP incorrecta en `.env` de PC3 o Kafka no está escuchando en 0.0.0.0:9092
- **Solución**: Verificar `.env` y configuración `KAFKA_LISTENERS`

#### Error: "No metadata available"
- **Causa**: `KAFKA_ADVERTISED_LISTENERS` incorrecto en PC2
- **Solución**: Verificar que `PC2_IP` en `.env` de PC2 es la IP real y coincide con `KAFKA_ADVERTISED_LISTENERS`

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

