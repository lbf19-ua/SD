# Análisis del Bucle de Eventos

## 🔄 Flujo Normal Esperado

### Al iniciar PC3 con 4 CPs:

1. **Cada Engine inicia** → envía **1 CP_REGISTRATION** con status='available'
   - Total: **4 eventos** (uno por cada CP)

2. **Central recibe cada CP_REGISTRATION**:
   - Registra el CP en BD
   - Publica **1 CP_INFO** al Monitor correspondiente
   - Total: **4 CP_INFO** publicados

3. **Monitors reciben CP_INFO**:
   - Solo actualizan estado local
   - **NO publican nada** (Monitors son consumidores pasivos)

4. **Resultado esperado**: 4 CP_REGISTRATION + 4 CP_INFO = **8 eventos totales**

---

## ⚠️ Posibles Causas de Bucles

### **Problema 1: Engine envía cp_status_change después de CP_REGISTRATION**

Si el Engine cambia su estado interno después de registrarse:
- Engine envía `CP_REGISTRATION` con status='available'
- Engine luego cambia estado internamente y envía `cp_status_change` también con status='available'
- Central recibe ambos eventos y publica `CP_INFO` dos veces

**Solución implementada**: 
- Engine ya incluye status='available' en CP_REGISTRATION
- Central ignora `cp_status_change` a 'available' si ocurre poco después de CP_REGISTRATION

### **Problema 2: Central publica CP_INFO múltiples veces para el mismo evento**

Central publica CP_INFO en muchos lugares:
- Al procesar `CP_REGISTRATION`
- Al procesar `cp_status_change`
- Al procesar `charging_started/stopped/completed`
- Al procesar `ENGINE_FAILURE/ENGINE_OFFLINE`

Si el mismo evento dispara múltiples llamadas a `publish_cp_info_to_monitor()`, se generan múltiples CP_INFO.

**Solución implementada**:
- Throttling: no publicar más de 1 vez cada 2 segundos por CP
- Verificación de cambios: solo publicar si el estado realmente cambió

### **Problema 3: Eventos antiguos de Kafka**

Si Kafka tiene mensajes antiguos en el topic y Central los consume:
- Central puede procesar eventos de sesiones anteriores
- Esto causa eventos duplicados o fuera de contexto

**Solución implementada**:
- `auto_offset_reset='latest'`: solo mensajes nuevos
- `group_id` único por inicio: no reutiliza offsets
- Filtro de timestamps: ignora eventos con más de 30s de antigüedad

### **Problema 4: Engine se reinicia y envía eventos múltiples veces**

Si el Engine se reinicia o hay problemas de conexión:
- Puede enviar `CP_REGISTRATION` múltiples veces
- Central puede procesar cada uno y publicar `CP_INFO` cada vez

**Solución implementada**:
- Flag `_registered` en Engine previene re-registros
- Deduplicación en Central por `message_id`
- Verificación de estado en BD antes de actualizar

---

## 🔍 Cómo Diagnosticar el Bucle

1. **Revisar logs de Central**:
   - Buscar líneas con `📨 Received event`
   - Ver cuántos eventos del mismo tipo llegan para el mismo CP
   - Verificar timestamps para identificar si son eventos antiguos

2. **Revisar logs de Engine**:
   - Buscar `📤 Published event`
   - Ver cuántas veces publica el mismo tipo de evento
   - Verificar si hay re-registros

3. **Revisar logs de Monitor**:
   - Buscar `📨 Evento recibido`
   - Ver si recibe múltiples CP_INFO para el mismo CP

---

## ✅ Verificaciones Actuales

- ✅ Engine solo se registra una vez (`_registered` flag)
- ✅ Central ignora eventos que ya procesó (`message_id` deduplication)
- ✅ Central ignora eventos antiguos (filtro de timestamp)
- ✅ Central tiene throttling para CP_INFO (2 segundos mínimo)
- ✅ Central verifica cambios reales antes de publicar CP_INFO
- ✅ Monitor NO publica eventos (solo consume)
- ✅ Central ignora CP_INFO que recibe (está en `events_to_ignore`)

---

## 🎯 Conclusión

Los bucles deberían estar prevenidos con las protecciones implementadas. Si aún ocurren, pueden deberse a:

1. **Múltiples instancias del mismo componente** corriendo simultáneamente
2. **Problemas de red** que causan retransmisiones de Kafka
3. **Eventos mal formateados** que no se detectan como duplicados
4. **Problemas de sincronización** donde el mismo evento se procesa en múltiples threads

Para diagnosticar, revisar los logs con el nuevo formato detallado que muestra:
- Tipo de evento
- CP_ID
- Message ID (para detectar duplicados)
- Timestamp (para detectar eventos antiguos)
- Source (para identificar quién lo envió)

