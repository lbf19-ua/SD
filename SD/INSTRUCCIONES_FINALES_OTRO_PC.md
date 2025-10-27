# ✅ Instrucciones para el Otro PC

## 📋 Resumen

Se corrigió `docker-compose.pc1.yml` para que Driver pueda conectar a Kafka. En Windows `network_mode: "host"` no funciona, así que se configuró con variables de entorno.

## 🔧 Cambios Realizados

### `docker-compose.pc1.yml`:
- Líneas 36-37: Port mapping normal (no host mode)
- Líneas 40-41: Variables de entorno:
  - `KAFKA_BROKER=192.168.1.235:9092` ← IP de tu PC (donde corre Central)
  - `CENTRAL_IP=192.168.1.235`

## 🚀 Pasos en el Otro PC

### 1. Detener Driver actual
```powershell
cd C:\ruta\al\SD\SD
docker-compose -f docker-compose.pc1.yml down
```

### 2. Copiar el archivo actualizado

**Opción A: Copiar desde USB** (más fácil)
- Copia `docker-compose.pc1.yml` desde tu USB al otro PC

**Opción B: Editar manualmente** (si no tienes USB)
- Abre `docker-compose.pc1.yml` en el otro PC
- Cambia estas líneas:

**ANTES (líneas 36-50):**
```yaml
container_name: ev-driver
ports:
  - "8001:8001"
environment:
  - WS_PORT=8001
  - PYTHONUNBUFFERED=1
```

**DESPUÉS:**
```yaml
container_name: ev-driver
# network_mode: "host"  # No funciona en Windows - usar mapeo de puertos normal
ports:
  - "8001:8001"
environment:
  # Kafka broker está en PC2
  - KAFKA_BROKER=192.168.1.235:9092
  - CENTRAL_IP=192.168.1.235
  - WS_PORT=8001
  - PYTHONUNBUFFERED=1
```

### 3. Verificar network_config.py

En el otro PC, edita `SD/network_config.py`:

```python
# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.235"  # ← Tu IP (donde corre Central)
```

### 4. Reiniciar Driver
```powershell
cd C:\ruta\al\SD\SD

# Reconstruir e iniciar
docker-compose -f docker-compose.pc1.yml up -d --build

# Ver logs para verificar conexión
docker logs ev-driver -f
```

## ✅ Verificación

**Debes ver en los logs:**
```
[DRIVER] ✅ Kafka producer and consumer initialized
[KAFKA] 📡 Consumer started, listening to ['central-events']
```

**NO debe aparecer:**
```
❌ NoBrokersAvailable
❌ cannot connect to kafka-broker
```

## 🎯 Prueba Final

1. Abre http://localhost:8001 en el otro PC
2. Login como `user1` / `pass1`
3. Click en "Start Charging"
4. En ESTE PC, ejecuta:
   ```powershell
   docker logs ev-central -f
   ```
5. Deberías ver:
   ```
   [KAFKA] 📨 Received event: AUTHORIZATION_REQUEST from topic: driver-events
   [CENTRAL] 🔐 Solicitud de autorización: usuario=user1, cp=CP01, client=abc123
   ```

## 🆘 Si Sigue Fallando

### Problema: NoBrokersAvailable

**Diagnosticar:**
```powershell
# En el otro PC:
Test-NetConnection 192.168.1.235 -Port 9092
```

**Si falla**: Firewall bloqueando
```powershell
# Como Admin en el otro PC:
New-NetFirewallRule -DisplayName "EV Kafka Out" -Direction Outbound -RemotePort 9092 -Protocol TCP -Action Allow
```

### Problema: "Kafka not available"

**Verificar variables:**
```powershell
docker exec ev-driver env | Select-String "KAFKA_BROKER"
# Debe mostrar: KAFKA_BROKER=192.168.1.235:9092
```

Si muestra otra cosa, reconstruir:
```powershell
docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc1.yml up -d --build
```

## 📊 Estado Esperado

### En el otro PC:
- ✅ Driver corriendo: `docker ps` muestra `ev-driver`
- ✅ Kafka conectado: Logs muestran "✅ Kafka producer initialized"
- ✅ Puede solicitar carga: Interface funciona

### En este PC (Central):
- ✅ Central corriendo: `docker ps` muestra `ev-central`
- ✅ Recibe eventos: Logs muestran "📨 Received event"
- ✅ Procesa autorizaciones: Logs muestran "🔐 Solicitud de autorización"

