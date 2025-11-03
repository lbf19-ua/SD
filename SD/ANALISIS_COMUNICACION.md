# Análisis del Flujo de Comunicación: Engine, Monitor, Driver ↔ Central

## Resumen del Flujo de Mensajes

### 1. ENGINE ↔ CENTRAL

#### ✅ Engine → Central (via `cp-events`)
Engine envía correctamente:
- `CP_REGISTRATION` con `action: 'connect'` - Auto-registro al iniciar
- `cp_status_change` - Cambios de estado del CP
- `charging_progress` - Actualizaciones cada segundo durante la carga
- `charging_completed` - Finalización de carga (desenchufe)

#### ✅ Central → Engine (via `central-events`)
Central envía correctamente y Engine procesa:
- `charging_started` con `action: 'charging_started'` ✅
- `charging_stopped` con `action: 'charging_stopped'` ✅
- `CP_ERROR_SIMULATED` con `action: 'cp_error_simulated'` ✅
- `CP_ERROR_FIXED` con `action: 'cp_error_fixed'` ✅
- `CP_STOP` con `action: 'stop'` ✅
- `CP_RESUME` with `action: 'resume'` ✅
- `CP_PLUG_IN` con `action: 'plug_in'` ✅
- `CP_UNPLUG` con `action: 'unplug'` ✅

**Estado**: ✅ **CORRECTO** - Engine escucha `central-events` y procesa todos los comandos correctamente.

---

### 2. MONITOR ↔ CENTRAL

#### ✅ Monitor → Central (via `monitor-events`)
Monitor envía correctamente:
- `MONITOR_AUTH` - Autenticación al iniciar
- `ENGINE_FAILURE` - Reporte de fallos del Engine
- `ENGINE_OFFLINE` - Reporte de Engine desconectado

#### ✅ Central → Monitor (via `central-events`)
Central envía correctamente y Monitor procesa:
- `CP_INFO` con `action: 'cp_info_update'` ✅
  - Monitor extrae datos de `event.data` correctamente
  - Maneja fallbacks si `data` está vacío
  - Actualiza `shared_state.cp_info` correctamente

**Estado**: ✅ **CORRECTO** - Monitor escucha `cp-events` y `central-events`, y procesa `CP_INFO` correctamente.

**Nota**: Monitor filtra eventos por `cp_id` para procesar solo eventos de su CP asignado (relación 1:1).

---

### 3. DRIVER ↔ CENTRAL

#### ✅ Driver → Central (via `driver-events`)
Driver envía correctamente:
- `AUTHORIZATION_REQUEST` - Solicitud de autorización de carga
- `CHARGING_TIMEOUT` - Timeout si CP no responde

#### ✅ Central → Driver (via `central-events`)
Central envía correctamente y Driver procesa:
- `AUTHORIZATION_RESPONSE` con `authorized: true/false` ✅
- `CP_ERROR_SIMULATED` ✅
- `CP_ERROR_FIXED` ✅
- `CHARGING_TICKET` ✅

#### ✅ Driver escucha `cp-events` para recibir:
- `charging_progress` del Engine ✅
  - Driver actualiza sesión local con energía y costo reales
  - Marca `cp_charging_confirmed = True` cuando recibe actualizaciones

**Estado**: ✅ **CORRECTO** - Driver escucha `central-events` y `cp-events`, y procesa todos los eventos correctamente.

---

## Problemas Identificados y Solucionados

### ❌ PROBLEMA 1: Central no procesaba mensajes de Engine
**Ubicación**: `EV_Central/EV_Central_WebSocket.py`, función `broadcast_kafka_event()`

**Problema**: 
- La función retornaba temprano (línea 1695-1697) si no había clientes WebSocket conectados
- Esto impedía procesar eventos importantes como `charging_progress`, `cp_status_change`, etc.

**Solución**: 
- Se movió la verificación de clientes conectados DESPUÉS del procesamiento de eventos
- Ahora los eventos se procesan SIEMPRE (actualización de BD, estados, etc.)
- Solo el broadcast a WebSocket se omite si no hay clientes

**Estado**: ✅ **SOLUCIONADO**

---

## Flujo Completo Verificado

### Flujo 1: Autorización y Inicio de Carga

1. **Driver** → `AUTHORIZATION_REQUEST` → `driver-events`
2. **Central** procesa y valida
3. **Central** → `AUTHORIZATION_RESPONSE` → `central-events` → ✅ Driver recibe
4. **Central** → `charging_started` → `central-events` → ✅ Engine recibe
5. **Engine** inicia carga y → `cp_status_change` → `cp-events` → ✅ Central procesa
6. **Engine** → `charging_progress` cada segundo → `cp-events` → ✅ Central procesa y actualiza BD
7. **Engine** → `charging_progress` → `cp-events` → ✅ Driver recibe y actualiza UI

### Flujo 2: Información del CP al Monitor

1. **Monitor** → `MONITOR_AUTH` → `monitor-events` → Central recibe
2. **Central** → `CP_INFO` → `central-events` → ✅ Monitor recibe
3. **Monitor** extrae datos de `event.data` y actualiza `shared_state.cp_info` ✅
4. **Monitor** actualiza dashboard inmediatamente ✅

### Flujo 3: Finalización de Carga

1. **Engine** → `charging_completed` → `cp-events` → ✅ Central procesa
2. **Central** finaliza sesión en BD y calcula costo ✅
3. **Central** → `CHARGING_TICKET` → `central-events` → ✅ Driver recibe
4. **Driver** muestra ticket al usuario ✅

---

## Verificación de Topics de Kafka

✅ **Engine** escucha: `central-events`
✅ **Engine** publica: `cp-events`
✅ **Monitor** escucha: `cp-events`, `central-events`
✅ **Monitor** publica: `monitor-events`
✅ **Driver** escucha: `central-events`, `cp-events`
✅ **Driver** publica: `driver-events`
✅ **Central** escucha: `driver-events`, `cp-events`, `monitor-events`
✅ **Central** publica: `central-events`

**Estado**: ✅ **TODOS LOS TOPICS CORRECTOS**

---

## Conclusión

✅ **Engine**: Escucha y procesa correctamente todos los comandos de Central
✅ **Monitor**: Escucha y procesa correctamente los eventos `CP_INFO` de Central
✅ **Driver**: Escucha y procesa correctamente todos los eventos de Central y Engine
✅ **Central**: Procesa correctamente todos los mensajes de Engine (problema solucionado)

**Estado General**: ✅ **SISTEMA FUNCIONAL** - Todos los componentes comunican correctamente.

