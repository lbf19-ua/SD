# 🧪 Test Final: Verificar Flujo Completo

## 📊 Estado Actual

- ✅ **Central (Este PC)**: Conectado a Kafka, escuchando eventos
- ✅ **Driver (Otro PC)**: Logs muestran que envía "Solicitando autorización"
- ❌ **Problema**: Central no muestra que recibe los eventos

## 🎯 Test Paso a Paso

### 1. En el otro PC (Driver):

**Abre la interfaz:**
```
http://localhost:8001
```

**Ejecuta en otra terminal (para ver logs):**
```powershell
docker logs ev-driver -f
```

### 2. En ESTE PC (Central):

**Abre otra terminal y ejecuta:**
```powershell
docker logs ev-central -f
```

### 3. En el otro PC (Driver):

1. Login como `user1` / `pass1`
2. Selecciona un CP (ej: CP_001)
3. Click en "Start Charging"
4. **ESPERA 5 segundos**

### 4. Verifica en ESTE PC (Central):

**Deberías ver en los logs:**
```
[KAFKA] 📨 Received event: AUTHORIZATION_REQUEST from topic: driver-events
[CENTRAL] 🔐 Solicitud de autorización: usuario=user1, cp=CP_001, client=abc123
```

### 5. Si NO aparece el mensaje:

**En el otro PC, verifica:**
```powershell
# Ver si el producer de Kafka está funcionando
docker exec ev-driver python -c "
from kafka import KafkaProducer
import json
p = KafkaProducer(bootstrap_servers='192.168.1.235:9092', value_serializer=lambda v: json.dumps(v).encode('utf-8'))
print('Enviando test...')
p.send('driver-events', {'test': 'mensaje de prueba'})
p.flush()
print('Enviado OK')
"

# En ESTE PC, deberías ver:
docker logs ev-central -f
# Debería mostrar el evento de prueba
```

## 🔍 Diagnóstico Rápido

**Ejecuta en el otro PC:**
```powershell
# Ver si el evento se envíó realmente
docker logs ev-driver | Select-String "Solicitando|send|producer" -Context 2

# Si no aparece nada después de "Solicitando autorización",
# entonces el producer no está enviando el evento a Kafka
```

## 💡 Posibles Causas

1. **Driver envía al topic equivocado**
   - Verifica: ¿envía a `driver-events`?
   
2. **Central no recibe por bucle while**
   - El bucle `for message in consumer:` podría estar bloqueado
   
3. **El evento no llega a Kafka**
   - Probar con Kafka UI: http://192.168.1.235:8080

## 🆘 Acción Inmediata

**Abre Kafka UI:**
```
http://192.168.1.235:8080
```

1. Ve a "Topics"
2. Busca `driver-events`
3. Click en el topic
4. Si intentas solicitar carga desde Driver, deberías ver mensajes apareciendo

**Si ves mensajes en Kafka UI pero NO en Central:**
→ El consumer de Central no está funcionando correctamente

**Si NO ves mensajes en Kafka UI:**
→ El Driver no está enviando a Kafka (problema de conexión o producer)

