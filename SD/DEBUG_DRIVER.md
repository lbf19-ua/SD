# 🔍 Debug: Driver no solicita carga

## ✅ Estado de Central (Este PC)

Central está funcionando correctamente:
```
[KAFKA] ✅ Connected to Kafka successfully!
[KAFKA] 📡 Consumer started, listening to ['driver-events', 'cp-events']
```

## 🔍 Verificación en el PC de Driver

### Paso 1: Ver logs de Driver

**En el otro PC, ejecuta:**
```powershell
docker logs ev-driver --tail=50
```

**Busca:**
- ✅ `[DRIVER] ✅ Kafka producer and consumer initialized`
- ✅ `[KAFKA] 📡 Consumer started, listening to ['central-events']`
- ❌ `[KAFKA] ⚠️ Warning: Kafka not available`

### Paso 2: Probar conectividad

**En el otro PC, ejecuta:**
```powershell
Test-NetConnection 192.168.1.235 -Port 9092
```

**Debe mostrar:** `TcpTestSucceeded : True`

Si falla:
```powershell
# Como Admin:
New-NetFirewallRule -DisplayName "EV Kafka Out" -Direction Outbound -RemotePort 9092 -Protocol TCP -Action Allow
```

### Paso 3: Verificar configuración de red

**En el otro PC, edita `SD/network_config.py`:**

```python
# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.235"  # ← Verifica que sea esta IP

# ====
KAFKA_BROKER = f"{PC2_IP}:9092"  # Debe ser: 192.168.1.235:9092
```

**Verificar:**
```powershell
docker exec ev-driver python -c "from network_config import KAFKA_BROKER, PC2_IP; print('PC2_IP:', PC2_IP); print('KAFKA_BROKER:', KAFKA_BROKER)"
```

### Paso 4: Probar envío manual

**En el otro PC, abrir Driver:**
1. Ir a http://localhost:8001
2. Login como `user1` / `pass1`
3. Click en "Select CP" y elegir cualquier CP
4. Click en "Start Charging"

**Mientras tanto, en ESTE PC, ver logs:**
```powershell
docker logs ev-central -f
```

**Debes ver:**
```
[KAFKA] 📨 Received event: AUTHORIZATION_REQUEST from topic: driver-events
[CENTRAL] 🔐 Solicitud de autorización: usuario=user1, cp=CP01, client=abc123
```

## 🐛 Problemas Comunes

### Problema 1: "NoBrokersAvailable" en Driver

**Síntoma:** Logs de Driver muestran "Kafka not available"

**Causa:** `KAFKA_BROKER` incorrecto o no accesible

**Solución:**
```powershell
# En el otro PC:
docker-compose -f docker-compose.pc1.yml down
# Editar docker-compose.pc1.yml - línea 40:
#   - KAFKA_BROKER=192.168.1.235:9092
docker-compose -f docker-compose.pc1.yml up -d --build
```

### Problema 2: Driver no envía el evento

**Síntoma:** Central no muestra "Received event"

**Causa:** Driver no está conectado a Kafka o tiene error en código

**Diagnosticar:**
```powershell
# En el otro PC:
docker exec ev-driver python -c "import sys; sys.path.append('/app'); from network_config import KAFKA_BROKER; from kafka import KafkaProducer; import json; p = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8')); print('Kafka OK')"
```

### Problema 3: Evento llega pero no se procesa

**Síntoma:** Central muestra "Received event" pero no procesa

**Causa:** Error en código de Central

**Ver logs de Central:**
```powershell
docker logs ev-central | Select-String "ERROR\|Exception\|Traceback"
```

## 📊 Checklist Rápido

**Ejecuta esto en el otro PC y compárteme el resultado:**

```powershell
# 1. Estado de contenedores
docker ps

# 2. Logs de Driver (últimas 30 líneas)
docker logs ev-driver --tail=30

# 3. Configuración de Kafka
docker exec ev-driver python -c "from network_config import KAFKA_BROKER, PC2_IP; print('PC2_IP:', PC2_IP); print('KAFKA_BROKER:', KAFKA_BROKER)"

# 4. Conectividad a Kafka
Test-NetConnection 192.168.1.235 -Port 9092

# 5. Si intentaste solicitar carga, ¿qué aparece en la interfaz?
# ¿Aparece algún mensaje? ¿Error? ¿Loading?
```

**Comparte estos 5 resultados y te digo exactamente qué está fallando.**

