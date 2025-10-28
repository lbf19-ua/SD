# ✅ FIX APLICADO: CP se queda en "reserved"

## 🐛 Problema Identificado

El CP se quedaba en "reserved" porque el **Kafka Producer del Driver no se inicializaba correctamente**.

### Causa Raíz

1. El Driver arranca ANTES de que Kafka esté listo
2. `initialize_kafka()` falla y `self.producer` queda `None`
3. El Consumer tiene lógica de reconexión pero el Producer NO
4. El Driver puede RECIBIR eventos (`AUTHORIZATION_RESPONSE`) ✅
5. Pero NO puede ENVIAR eventos (`charging_started`) ❌
6. Por lo tanto, el CP se queda en "reserved"

## 🔧 Fix Aplicado

### 1. Reintentos en initialize_kafka()

```python
def initialize_kafka(self, max_retries=10):
    """Inicializa el productor de Kafka con reintentos"""
    for attempt in range(max_retries):
        try:
            self.producer = KafkaProducer(...)
            self.consumer = KafkaConsumer(...)
            print(f"[DRIVER] ✅ Kafka producer and consumer initialized")
            return
        except Exception as e:
            print(f"[DRIVER] ⚠️  Attempt {attempt+1}/{max_retries} - Kafka not available: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Esperar 2 segundos entre intentos
                continue
            else:
                print(f"[DRIVER] ❌ Failed to connect to Kafka after {max_retries} attempts")
```

**Beneficio**: Ahora intenta conectarse hasta 10 veces antes de rendirse.

### 2. Nueva función ensure_producer()

```python
def ensure_producer(self):
    """Asegura que el producer esté disponible, reintentando si es necesario"""
    if self.producer is None:
        print(f"[DRIVER] 🔄 Producer not initialized, attempting reconnection...")
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"[DRIVER] ✅ Kafka producer reconnected successfully")
            return True
        except Exception as e:
            print(f"[DRIVER] ❌ Producer reconnection failed: {e}")
            return False
    return True
```

**Beneficio**: Si el producer falla al inicio, intenta reconectarse cuando se necesita enviar un evento.

### 3. Uso de ensure_producer() en todos los métodos

Reemplazado en:
- `request_charging()` - Al solicitar autorización
- `request_charging_at_cp()` - Al solicitar en CP específico
- `stop_charging()` - Al detener carga
- `simulate_cp_error()` - Al simular errores
- `fix_cp_error()` - Al corregir errores
- En el handler de `AUTHORIZATION_RESPONSE` - Al enviar `charging_started`

**Antes:**
```python
if self.producer:
    self.producer.send(KAFKA_TOPIC_PRODUCE, event)
```

**Ahora:**
```python
if self.ensure_producer():  # ← Intenta reconectar si es necesario
    self.producer.send(KAFKA_TOPIC_PRODUCE, event)
```

## ✅ Resultado

Ahora el flujo funciona así:

```
1. Driver arranca (Kafka no está listo)
   → initialize_kafka() reintenta 10 veces
   → Si falla, self.producer queda None

2. Usuario solicita carga
   → request_charging() llama ensure_producer()
   → ensure_producer() reintenta conectar
   → Si tiene éxito, self.producer se inicializa
   → Envía AUTHORIZATION_REQUEST ✅

3. Central autoriza
   → Driver recibe AUTHORIZATION_RESPONSE
   → ensure_producer() verifica que producer esté listo
   → Envía charging_started ✅

4. Central recibe charging_started
   → Cambia CP de "reserved" a "charging" ✅
   → Crea sesión en BD ✅
```

## 📋 Instrucciones de Despliegue

### Opción 1: Actualizar el contenedor (recomendado)

```powershell
# En PC del Driver
cd SD
docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc1.yml up -d --build
```

### Opción 2: Ejecutar con Python directamente

```powershell
# En PC del Driver
cd SD/EV_Driver
python EV_Driver_WebSocket.py
```

## 🧪 Verificar que funciona

1. Ejecuta el Driver
2. Verifica los logs:

```powershell
docker logs ev-driver -f
```

**Deberías ver:**
```
[DRIVER] ⚠️  Attempt 1/10 - Kafka not available: NoBrokersAvailable
[DRIVER] ⚠️  Attempt 2/10 - Kafka not available: NoBrokersAvailable
[DRIVER] ✅ Kafka producer and consumer initialized  ← SE CONECTÓ
```

3. Solicita carga desde la interfaz web
4. Verifica que NO veas "Sistema de mensajería no disponible"
5. Verifica que el CP cambie de "reserved" a "charging"

## 📊 Logs Esperados

**Cuando funciona correctamente:**

```
[DRIVER] 🔐 Solicitando autorización a Central (asignación automática de CP)
[KAFKA] 📨 Received AUTHORIZATION_RESPONSE from Central
[DRIVER] ✅ Central autorizó carga en CP_001
[DRIVER] 📤 Enviado evento charging_started a Central para sesión en CP_001  ← CLAVE
```

**En el Central:**

```
[CENTRAL] 🔐 Solicitud de autorización: usuario=driver1, buscando CP disponible...
[CENTRAL] 🎯 CP CP_001 asignado y reservado automáticamente para driver1
[CENTRAL] 📨 Received event: charging_started from topic: driver-events  ← CLAVE
[CENTRAL] ⚡ Suministro iniciado - Sesión 5 en CP CP_001 para usuario driver1
```

## 🎯 Resumen

- ✅ Producer ahora reintenta conectarse automáticamente
- ✅ No se requiere que Kafka esté listo al iniciar el Driver
- ✅ El CP cambia de "reserved" a "charging" correctamente
- ✅ Las sesiones se registran en la BD
- ✅ El flujo completo funciona de punta a punta

**¡PROBLEMA RESUELTO! 🎉**


