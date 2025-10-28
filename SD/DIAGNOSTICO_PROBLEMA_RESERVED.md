# 🔍 DIAGNÓSTICO: CP se queda en "reserved"

## 🧩 Análisis del Flujo

### Flujo Esperado

```
1. Driver → Kafka: AUTHORIZATION_REQUEST
2. Central recibe y marca CP como "reserved"
3. Central → Kafka: AUTHORIZATION_RESPONSE (authorized=true)
4. Driver recibe AUTHORIZATION_RESPONSE
5. Driver → Kafka: charging_started  ⚠️ AQUÍ ESTÁ EL PROBLEMA
6. Central recibe charging_started y cambia CP: "reserved" → "charging"
```

## 🐛 El Problema

El CP se queda en "reserved" porque **el paso 5 no ocurre**.

### Código del Driver (líneas 111-125)

```python
if self.producer:  # ← PROBLEMA AQUÍ
    start_event = {
        'message_id': generate_message_id(),
        'event_type': 'charging_started',
        'action': 'charging_started',
        'driver_id': self.driver_id,
        'username': username,
        'user_id': auth_data['user_id'],
        'cp_id': cp_id,
        'correlation_id': correlation_id,
        'timestamp': current_timestamp()
    }
    self.producer.send(KAFKA_TOPIC_PRODUCE, start_event)
    self.producer.flush()
    print(f"[DRIVER] 📤 Enviado evento charging_started a Central para sesión en {cp_id}")
```

**SI `self.producer` ES `None`, NO SE ENVÍA EL EVENTO**

### ¿Cuándo self.producer es None?

En `initialize_kafka()` (líneas 65-81):

```python
def initialize_kafka(self):
    """Inicializa el productor de Kafka"""
    try:
        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_broker,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.consumer = KafkaConsumer(
            *KAFKA_TOPICS_CONSUME,
            bootstrap_servers=self.kafka_broker,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            group_id=f'ev_driver_group_{self.driver_id}'
        )
        print(f"[DRIVER] ✅ Kafka producer and consumer initialized")
    except Exception as e:
        print(f"[DRIVER] ⚠️  Warning: Kafka not available: {e}")
        # ← AQUÍ self.producer y self.consumer quedan None
```

**Si Kafka no está accesible al iniciar el Driver, `self.producer` queda `None`**

## ✅ Evidencia en los Logs

En los logs del Driver vimos:

```
[DRIVER] ⚠️  Warning: Kafka not available: NoBrokersAvailable
```

Esto significa que cuando el Driver arrancó, **NO pudo conectarse a Kafka**.

Por lo tanto:
- ✅ `self.producer = None`
- ❌ NO puede enviar `charging_started`
- ❌ El CP se queda en "reserved"

## 🔧 ¿Por qué el Consumer SÍ funciona pero el Producer NO?

**TRUCO DEL CÓDIGO**: En `kafka_listener()` (línea 163-173):

```python
except Exception as e:
    print(f"[KAFKA] ⚠️ Consumer error: {e}")
    # Intentar reconectar
    try:
        self.consumer = KafkaConsumer(
            *KAFKA_TOPICS_CONSUME,
            bootstrap_servers=self.kafka_broker,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            group_id=f'ev_driver_group_{self.driver_id}'
        )
    except:
        pass
```

**El consumer tiene lógica de reconexión automática, pero el producer NO**.

Entonces:
- El Consumer se reconecta automáticamente y recibe `AUTHORIZATION_RESPONSE` ✅
- El Producer nunca se inicializa correctamente ❌
- Por eso el Driver puede RECIBIR eventos pero NO ENVIAR

## 🎯 Solución

### Opción 1: Agregar reconexión al Producer

Modificar `EV_Driver_WebSocket.py` para reintentar la conexión del producer cuando falla:

```python
def ensure_producer(self):
    """Asegura que el producer esté inicializado, reintentando si es necesario"""
    if self.producer is None:
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"[DRIVER] ✅ Kafka producer reconnected")
        except Exception as e:
            print(f"[DRIVER] ⚠️  Producer still unavailable: {e}")
            return False
    return True
```

Y luego en `request_charging` (línea 233):

```python
if self.ensure_producer():  # ← CAMBIAR AQUÍ
    event = {
        'message_id': generate_message_id(),
        ...
```

### Opción 2: Ejecutar el Driver DESPUÉS de Kafka

El problema es que el Driver arranca ANTES de que Kafka esté listo.

**Solución**: Esperar a que Kafka esté disponible antes de iniciar el Driver.

### Opción 3: Agregar retry en initialize_kafka

Modificar `initialize_kafka()` para reintentar varias veces:

```python
def initialize_kafka(self, max_retries=10):
    """Inicializa el productor de Kafka con reintentos"""
    for attempt in range(max_retries):
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            self.consumer = KafkaConsumer(
                *KAFKA_TOPICS_CONSUME,
                bootstrap_servers=self.kafka_broker,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                group_id=f'ev_driver_group_{self.driver_id}'
            )
            print(f"[DRIVER] ✅ Kafka producer and consumer initialized")
            return
        except Exception as e:
            print(f"[DRIVER] ⚠️  Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                print(f"[DRIVER] ❌ Failed to connect to Kafka after {max_retries} attempts")
```

## 🧪 Verificar el Problema

Ejecuta en el PC del Driver:

```powershell
docker logs ev-driver | Select-String "Kafka|producer"
```

Si ves:
```
[DRIVER] ⚠️  Warning: Kafka not available: NoBrokersAvailable
```

**ESE ES EL PROBLEMA**.

## 📊 Logs Completos del Flujo

**Driver (cuando falla):**
```
[DRIVER] ⚠️  Warning: Kafka not available: NoBrokersAvailable
[DRIVER] 🔐 Solicitando autorización...
[KAFKA] 📨 Received AUTHORIZATION_RESPONSE from Central
[DRIVER] ✅ Central autorizó carga en CP_001
# ← AQUÍ DEBERÍA VER: [DRIVER] 📤 Enviado evento charging_started
# ← PERO NO APARECE PORQUE self.producer es None
```

**Central:**
```
[CENTRAL] 🔐 Solicitud de autorización: usuario=driver1, buscando CP disponible...
[CENTRAL] 🎯 CP CP_001 asignado y reservado automáticamente para driver1
# ← AQUÍ DEBERÍA VER: [CENTRAL] 📨 Received event: charging_started
# ← PERO NUNCA LLEGA
# ← Por lo tanto, el CP se queda en "reserved"
```

## ✅ Solución Inmediata

1. **Reiniciar el Driver** después de que Kafka esté corriendo:

```powershell
# En PC del Driver
docker restart ev-driver

# Ver logs para verificar que se conectó
docker logs ev-driver -f
```

Deberías ver:
```
[DRIVER] ✅ Kafka producer and consumer initialized
```

2. **Si sigue fallando**, verifica la IP de Kafka en `docker-compose.pc1.yml`:

```yaml
environment:
  - KAFKA_BROKER=172.20.10.8:9092  # ← DEBE ser la IP del Central
```

3. **Mejor opción**: Ejecuta el Driver con Python directo (sin Docker):

```powershell
cd SD/EV_Driver
python EV_Driver_WebSocket.py
```

Esto evita problemas de red de Docker.


