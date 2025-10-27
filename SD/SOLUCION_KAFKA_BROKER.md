# ✅ SOLUCIÓN: Error "kafka-broker" en el otro PC

## 🔍 Problema Identificado

**Error**: Driver y Monitor no pueden conectar a Kafka en el otro PC.
**Causa**: El `docker-compose.pc1.yml` NO tenía `network_mode: "host"`.
**Efecto**: Los contenedores Docker están aislados de la red del host, no pueden alcanzar `192.168.1.235:9092`.

## ✅ Solución Aplicada

### 1. En `docker-compose.pc1.yml`:
```yaml
ev-driver:
  ...
  network_mode: "host"  # ✅ AGREGADO - Permite acceso a red del host
  # Eliminado: ports (no se necesita con network_mode: host)
  # Eliminado: extra_hosts (no se necesita con network_mode: host)
```

### 2. En `docker-compose.pc3.yml`:
```yaml
ev-monitor:
  ...
  network_mode: "host"  # ✅ Ya estaba, pero verificado
```

## 🚀 Pasos para Aplicar en el Otro PC

### Paso 1: Detener contenedores actuales
```powershell
cd C:\ruta\al\SD\SD

docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc3.yml down
```

### Paso 2: Copiar los archivos actualizados

**Desde este PC, copiar a USB:**
- `SD/docker-compose.pc1.yml`
- `SD/docker-compose.pc3.yml`
- `SD/network_config.py`

**O modificar en el otro PC:**
```powershell
# En el otro PC, en docker-compose.pc1.yml:
# Cambiar la línea 35 de:
    container_name: ev-driver
    ports:
      - "8001:8001"
# A:
    container_name: ev-driver
    network_mode: "host"
# Y eliminar las líneas de ports, extra_hosts
```

### Paso 3: Reiniciar con nueva configuración
```powershell
cd C:\ruta\al\SD\SD

# Iniciar Driver
docker-compose -f docker-compose.pc1.yml up -d --build

# Ver logs inmediatos
docker logs ev-driver -f

# Si todo bien, iniciar Monitor
docker-compose -f docker-compose.pc3.yml up -d --build
```

## ✅ Verificación

**En los logs de Driver debes ver:**
```
[DRIVER] ✅ Kafka producer and consumer initialized
[KAFKA] 📡 Consumer started, listening to ['central-events']
```

**Ya NO debe aparecer:**
```
❌ NoBrokersAvailable
❌ cannot connect to kafka-broker
```

## 📊 Estado Esperado

### En el otro PC:
```powershell
docker ps
# Debe mostrar:
# ev-driver (Up) - network_mode: host
# ev-monitor (Up) - network_mode: host

docker logs ev-driver | Select-String "Kafka"
# Debe mostrar: "✅ Kafka producer and consumer initialized"
```

### En este PC (Central):
```powershell
docker logs ev-central -f
# Cuando Driver envíe solicitud, verás:
# [KAFKA] 📨 Received event: AUTHORIZATION_REQUEST from topic: driver-events
```

## ⚠️ Importante

Con `network_mode: "host"`:
- ✅ Los contenedores pueden acceder directamente a la red del PC
- ✅ Pueden conectar a `192.168.1.235:9092` sin problemas
- ✅ El puerto 8001/8003 está expuesto directamente en el host
- ⚠️ El firewall del host debe permitir esos puertos

**Verifica firewall:**
```powershell
# En el otro PC (como Admin):
New-NetFirewallRule -DisplayName "EV Driver" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV Monitor" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
```

## 🎯 Próximo Paso

**Después de aplicar estos cambios en el otro PC:**
1. Driver debe poder conectar a Kafka ✅
2. Monitor debe poder conectar a Kafka ✅
3. Las solicitudes de carga deben llegar a Central ✅

**Para verificar:**
- Abre http://localhost:8001 en el otro PC
- Login como `user1` / `pass1`
- Haz clic en "Start Charging"
- Mira los logs de Central: `docker logs ev-central -f`

