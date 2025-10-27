# 🔍 Verificar Comunicación Driver → Central

## Estado Actual
- **Central (PC2)**: ✅ Corriendo, conectado a Kafka
- **Driver**: Necesita verificar en el otro PC
- **Error**: Driver no está enviando solicitudes o Central no las recibe

## Pasos para Diagnosticar

### 1. En el PC de Driver (donde corre Driver):

```powershell
# Ver logs de Driver
docker logs ev-driver -f

# Verificar que Driver pueda conectarse a Kafka
docker exec ev-driver ping -c 3 192.168.1.235
```

### 2. En este PC (Central):

```powershell
# Ver logs de Central en tiempo real
docker logs ev-central -f

# Verificar que Central está escuchando Kafka
docker logs ev-central | Select-String "KAFKA"
```

### 3. Verificar Topics de Kafka:

```powershell
# Listar topics
docker exec ev-kafka-broker kafka-topics.sh --bootstrap-server localhost:29092 --list

# Ver mensajes del topic driver-events
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events --from-beginning
```

## Problemas Comunes

### ❌ Driver no puede conectar a Kafka
**Síntoma**: "NoBrokersAvailable" en logs de Driver
**Causa**: Network config incorrecta o firewall
**Solución**: 
```powershell
# En el PC de Driver, verificar network_config.py
# Debe tener: PC2_IP = "192.168.1.235"

# Verificar conectividad
Test-NetConnection 192.168.1.235 -Port 9092
```

### ❌ Central no recibe eventos
**Síntoma**: Central escucha pero no muestra "[KAFKA] 📨 Received"
**Causa**: Driver no está enviando o Kafka no entrega
**Solución**:
```powershell
# Verificar que el consumer de Central está activo
docker logs ev-central | Select-String "Consumer started"

# Probar enviar mensaje manual
docker exec ev-kafka-broker kafka-console-producer.sh --bootstrap-server localhost:29092 --topic driver-events
# (luego escribir: {"event_type": "test", "cp_id": "CP01"})
```

### ❌ Driver usa base de datos en vez de Kafka
**Síntoma**: Driver intenta acceder a BD antes de enviar a Central
**Causa**: Código legacy en Driver
**Solución**: Ya corregido en el código actual

## Estado del Código

✅ **Central (EV_Central_WebSocket.py)**:
- Línea 571-607: Consumer de Kafka con reintentos
- Línea 649-703: Procesa `AUTHORIZATION_REQUEST`
- Línea 630-703: Responde con `AUTHORIZATION_RESPONSE`

✅ **Driver (EV_Driver_WebSocket.py)**:
- Línea 217-307: `request_charging()` envía `AUTHORIZATION_REQUEST`
- Línea 273-285: Crea evento y lo envía a Kafka
- Línea 80-120: `kafka_listener()` espera `AUTHORIZATION_RESPONSE`

## Comando Rápido de Prueba

```powershell
# En Driver PC:
# 1. Login como user1
# 2. Seleccionar un CP disponible
# 3. Click "Start Charging"
# 4. Ver logs: docker logs ev-driver -f

# En Central PC:
# 5. Ver logs: docker logs ev-central -f
# 6. Deberías ver: "[CENTRAL] 🔐 Solicitud de autorización..."
```

## ¿Qué revisar ahora?

1. **¿Driver está corriendo?**: `docker ps` en el otro PC
2. **¿Network config es correcta?**: `PC2_IP = "192.168.1.235"` en el otro PC
3. **¿Firewall permite conexión?**: Probar `Test-NetConnection` desde otro PC
4. **¿Kafka recibe los mensajes?**: Ver `docker logs ev-kafka-broker`

