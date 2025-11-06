# 📋 Guía para Agregar Nuevos Puntos de Carga (CPs)

## ⚠️ Problema Actual

Cuando ejecutas un nuevo Engine/Monitor **sin registrar el CP primero**, aparecen estos errores:

```
[CENTRAL] ⚠️ CP CP_999 no existe en BD, omitiendo CP_INFO
[CENTRAL] ⚠️ ENGINE_FAILURE recibido: cp=CP_999, type=unknown, failures=3
```

**Causa**: El CP no existe en la base de datos, por lo que Central no puede procesarlo correctamente.

---

## ✅ Solución: Orden Correcto de Ejecución

### **Opción 1: Auto-Registro (Recomendado)**

Los Engines están configurados para auto-registrarse cuando se conectan. **PERO** necesitas que Central esté corriendo primero:

#### **Paso 1: Asegúrate que Central esté corriendo**
```powershell
docker logs ev-central -f
# Deberías ver: [CENTRAL] ✅ Kafka producer initialized
```

#### **Paso 2: Ejecuta el Engine (se auto-registrará)**
```powershell
docker run -d `
  --name sd-cp-engine-222 `
  --network ev-network `
  -p 5122:5100 `
  -e CP_ID=CP_222 `
  -e LOCATION="EPS IV" `
  -e HEALTH_PORT=5100 `
  -e KAFKA_BROKER=192.168.1.42:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v "${PWD}\ev_charging.db:/app/ev_charging.db" `
  -v "${PWD}\network_config.py:/app/network_config.py" `
  -v "${PWD}\database.py:/app/database.py" `
  -v "${PWD}\event_utils.py:/app/event_utils.py" `
  --restart unless-stopped `
  sd-ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_222 --location "EPS IV" --health-port 5100 --kafka-broker 192.168.1.42:9092
```

**Espera a ver en los logs de Central**:
```
[CENTRAL] 🆕 Auto-reg CP on connect: cp_id=CP_999, loc=EPS IV, ...
[CENTRAL] ✅ CP registrado/actualizado: CP_999 en 'EPS IV' estado=available
```

#### **Paso 3: Ahora ejecuta el Monitor**
```powershell
docker run -d `
  --name ev-cp-monitor-222 `
  --network ev-network `
  -p 5522:5500 `
  -e CP_ID=CP_999 `
  -e ENGINE_HOST=sd-cp-engine-222 `
  -e ENGINE_PORT=5100 `
  -e MONITOR_PORT=5500 `
  -e KAFKA_BROKER=192.168.1.42:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v "${PWD}\ev_charging.db:/app/ev_charging.db:ro" `
  -v "${PWD}\network_config.py:/app/network_config.py:ro" `
  -v "${PWD}\database.py:/app/database.py:ro" `
  -v "${PWD}\event_utils.py:/app/event_utils.py:ro" `
  -v "${PWD}\EV_CP_M\monitor_dashboard.html:/app/monitor_dashboard.html:ro" `
  --restart unless-stopped `
  sd-ev-cp-monitor-001 `
  python -u EV_CP_M_WebSocket.py --cp-id CP_222 --engine-host sd-cp-engine-222 --engine-port 5100 --monitor-port 5500 --kafka-broker 192.168.1.42:9092
```

---

### **Opción 2: Registro Manual desde Dashboard Admin**

Si prefieres registrar manualmente antes de ejecutar el Engine:

#### **Paso 1: Abre el Dashboard de Central**
```
http://192.168.1.42:5511
```

#### **Paso 2: Registra el nuevo CP**
- Busca el botón "➕ Registrar Nuevo CP"
- Completa el formulario:
  - **CP ID**: `CP_999`
  - **Ubicación**: `EPS IV`
  - **Potencia Máxima**: `22` kW
  - **Tarifa**: `0.35` €/kWh
- Clic en "Registrar"

#### **Paso 3: Ejecuta Engine y Monitor**
Usa los mismos comandos de la Opción 1, pasos 2 y 3.

---

## 🔍 Verificar que Funcionó Correctamente

### **1. Verificar en logs de Central**
```powershell
docker logs ev-central --tail 50
```

**Deberías ver**:
```
[CENTRAL] 🆕 Auto-reg CP on connect: cp_id=CP_999, loc=EPS IV
[CENTRAL] ✅ CP registrado/actualizado: CP_999 en 'EPS IV' estado=available
[CENTRAL] 📡 CP_INFO enviado al Monitor - CP: CP_999, Location: 'EPS IV', Status: available
```

### **2. Verificar en logs del Engine**
```powershell
docker logs sd-cp-engine-999 --tail 30
```

**Deberías ver**:
```
[CP_999] ✅ Kafka producer initialized
[CP_999] 🆕 Auto-registering with Central...
[CP_999] ✅ Registration request sent to Central (status: available)
[CP_999] 📤 Published event: CP_REGISTRATION
[CP_999] ✅ Health check server started on port 5100
[CP_999] 🔄 Listening for commands from Central...
```

### **3. Verificar en Dashboard de Monitor**
```
http://localhost:5511
```

Deberías ver el nuevo CP listado con estado `AVAILABLE` (verde).

---

## ❌ Errores Comunes y Soluciones

### **Error 1: "CP_999 no existe en BD"**
**Causa**: Ejecutaste el Engine antes que Central se inicializara completamente.

**Solución**:
```powershell
# Detener y eliminar el Engine
docker stop sd-cp-engine-999
docker rm sd-cp-engine-999

# Esperar 5 segundos
Start-Sleep -Seconds 5

# Volver a ejecutarlo
docker run -d ... (comando completo)
```

---

### **Error 2: "ENGINE_FAILURE recibido: cp=CP_999, type=unknown"**
**Causa**: El CP no está registrado cuando el Monitor intenta conectarse.

**Solución**: Asegúrate que el **Engine se ejecutó primero** (auto-registro) antes del Monitor.

---

### **Error 3: Monitor muestra "OFFLINE Desconocido"**
**Causa**: El Engine no se auto-registró correctamente o no hay conexión con Kafka.

**Solución**:
```powershell
# Verificar que Kafka está corriendo
docker ps | Select-String kafka

# Verificar logs del Engine
docker logs sd-cp-engine-999 --tail 50

# Si no ves "Registration request sent", reiniciar:
docker restart sd-cp-engine-999
```

---

## 📝 Plantilla de Comandos para Nuevos CPs

Copia y modifica estos comandos según necesites:

```powershell
# ========================================
# PASO 1: CREAR ENGINE (auto-registro)
# ========================================
docker run -d `
  --name sd-cp-engine-XXX `
  --network ev-network `
  -p PUERTO_EXTERNAL:5100 `
  -e CP_ID=CP_XXX `
  -e LOCATION="UBICACION" `
  -e HEALTH_PORT=5100 `
  -e KAFKA_BROKER=192.168.1.42:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v "${PWD}\ev_charging.db:/app/ev_charging.db" `
  -v "${PWD}\network_config.py:/app/network_config.py" `
  -v "${PWD}\database.py:/app/database.py" `
  -v "${PWD}\event_utils.py:/app/event_utils.py" `
  --restart unless-stopped `
  sd-ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_XXX --location "UBICACION" --health-port 5100 --kafka-broker 192.168.1.42:9092

# ========================================
# PASO 2: ESPERAR Y VERIFICAR AUTO-REGISTRO
# ========================================
Start-Sleep -Seconds 5
docker logs ev-central --tail 20 | Select-String "CP_XXX"

# ========================================
# PASO 3: CREAR MONITOR
# ========================================
docker run -d `
  --name ev-cp-monitor-XXX `
  --network ev-network `
  -p PUERTO_MONITOR:5500 `
  -e CP_ID=CP_XXX `
  -e ENGINE_HOST=sd-cp-engine-XXX `
  -e ENGINE_PORT=5100 `
  -e MONITOR_PORT=5500 `
  -e KAFKA_BROKER=192.168.1.42:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v "${PWD}\ev_charging.db:/app/ev_charging.db:ro" `
  -v "${PWD}\network_config.py:/app/network_config.py:ro" `
  -v "${PWD}\database.py:/app/database.py:ro" `
  -v "${PWD}\event_utils.py:/app/event_utils.py:ro" `
  -v "${PWD}\EV_CP_M\monitor_dashboard.html:/app/monitor_dashboard.html:ro" `
  --restart unless-stopped `
  sd-ev-cp-monitor-001 `
  python -u EV_CP_M_WebSocket.py --cp-id CP_XXX --engine-host sd-cp-engine-XXX --engine-port 5100 --monitor-port 5500 --kafka-broker 192.168.1.42:9092
```

**Reemplaza**:
- `XXX` → Número del CP (ej: `111`, `999`)
- `UBICACION` → Ubicación física (ej: `"EPS IV"`, `"Parking Norte"`)
- `PUERTO_EXTERNAL` → Puerto externo del Engine (ej: `5188`, `5111`)
- `PUERTO_MONITOR` → Puerto externo del Monitor (ej: `5511`, `5522`)

---

## ✅ Checklist Final

Antes de ejecutar, verifica:

- [ ] Central está corriendo (`docker ps | Select-String central`)
- [ ] Kafka está corriendo (`docker ps | Select-String kafka`)
- [ ] El CP_ID es único (no se repite con otros CPs)
- [ ] Los puertos externos no están en uso
- [ ] La ubicación (LOCATION) está entre comillas si tiene espacios

---

## 🎯 Resumen del Orden Correcto

```
1. Central CORRIENDO ✅
   ↓
2. Ejecutar ENGINE (se auto-registra) ✅
   ↓
3. Verificar en logs que se registró ✅
   ↓
4. Ejecutar MONITOR ✅
   ↓
5. Verificar en Dashboard ✅
```

**¡Nunca ejecutes Monitor antes que Engine se haya auto-registrado!**
