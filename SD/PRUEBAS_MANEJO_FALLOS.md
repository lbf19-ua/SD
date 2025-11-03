# 🧪 Guía de Pruebas - Manejo de Fallos y Estados Combinados

Este documento explica cómo probar todas las funcionalidades implementadas relacionadas con:
1. **Estados combinados del Monitor y Engine**
2. **Manejo de fallos en cada componente**

---

## 📋 Requisitos Implementados

### ✅ 1. Estados Combinados (Monitor + Engine)

**Tabla de Estados:**
- **Monitor_OK + Engine_OK** → `available` (Verde)
- **Monitor_OK + Engine_KO** → `fault` (Rojo)
- **Monitor_KO + Engine_OK** → `offline` (Desconectado)
- **Monitor_KO + Engine_KO** → `offline` (Desconectado)

### ✅ 2. Manejo de Fallos

- **Monitor se desconecta**: Central marca CP como "Desconectado", finaliza sesiones activas
- **Engine se cae**: Monitor detecta y reporta, Central marca como "Averiado", notifica Driver
- **Driver se cierra**: El servicio continúa, Driver puede ver resultado al reconectarse
- **Central se cae**: Los CPs continúan cargando hasta finalizar, luego se paran

---

## 🧪 Pruebas Paso a Paso

### **Prueba 1: Estados Combinados - Monitor_OK + Engine_OK**

**Objetivo:** Verificar que cuando ambos están OK, el CP está `available`.

**Pasos:**
1. Iniciar Central:
   ```bash
   cd SD/SD/EV_Central
   python EV_Central_WebSocket.py
   ```

2. Iniciar Engine (CP_001):
   ```bash
   cd SD/SD/EV_CP_E
   python EV_CP_E.py --cp-id CP_001 --location "Test Location"
   ```

3. Iniciar Monitor para CP_001:
   ```bash
   cd SD/SD/EV_CP_M
   python EV_CP_M_WebSocket.py --cp-id CP_001 --engine-port 5100
   ```

4. **Verificar en Central:**
   - Abrir dashboard: http://localhost:8002
   - El CP_001 debe aparecer como **Verde** (`available`)
   - En logs de Central, buscar:
     ```
     [CENTRAL] ✅ Monitor OK detectado para CP_001
     [CENTRAL] 🔄 Estado combinado actualizado para CP_001: offline → available (Monitor_OK + Engine_OK)
     ```

5. **Verificar heartbeats:**
   - En logs del Monitor, cada 10 segundos debe aparecer:
     ```
     [MONITOR-CP_001] 💓 Heartbeat sent to Central (Engine: OK)
     ```

**Resultado esperado:** CP_001 aparece como `available` (Verde) en Central.

---

### **Prueba 2: Estados Combinados - Monitor_OK + Engine_KO**

**Objetivo:** Verificar que cuando Engine está KO, el CP está `fault`.

**Pasos:**
1. Con el sistema funcionando (Monitor_OK + Engine_OK), simular fallo en Engine:
   - En el Engine, presionar `F` (Fault) en el menú CLI, O
   - En Central dashboard, usar "Simular Error" → `fault`

2. El Engine responderá "KO" a los health checks del Monitor.

3. **Verificar en logs del Monitor:**
   ```
   [MONITOR-CP_001] ⚠️ Health check KO (failure 1/3)
   [MONITOR-CP_001] ⚠️ Health check KO (failure 2/3)
   [MONITOR-CP_001] ⚠️ Health check KO (failure 3/3)
   [MONITOR-CP_001] 🚨 3+ consecutive failures, reporting to Central
   [MONITOR-CP_001] 📤 ENGINE_FAILURE reported to Central
   ```

4. **Verificar en Central:**
   - En logs:
     ```
     [CENTRAL] 🚨 ENGINE_FAILURE recibido: cp=CP_001
     [CENTRAL] 🔄 Estado combinado actualizado para CP_001: available → fault (Monitor_OK + Engine_KO)
     ```
   - En dashboard: CP_001 debe aparecer como **Rojo** (`fault`)

5. **Verificar heartbeat incluye estado KO:**
   - En logs del Monitor:
     ```
     [MONITOR-CP_001] 💓 Heartbeat sent to Central (Engine: KO)
     ```

**Resultado esperado:** CP_001 aparece como `fault` (Rojo) en Central.

---

### **Prueba 3: Estados Combinados - Monitor_KO + Engine_OK**

**Objetivo:** Verificar que cuando Monitor está KO, el CP está `offline` aunque Engine esté OK.

**Pasos:**
1. Con el sistema funcionando (Monitor_OK + Engine_OK), **detener el Monitor** (Ctrl+C).

2. **Esperar 30 segundos** (tiempo de timeout de heartbeat).

3. **Verificar en Central:**
   - En logs (cada 15 segundos):
     ```
     [CENTRAL] 🚨 Monitor KO detectado para CP_001 (sin heartbeat por 35.2s)
     [CENTRAL] 🔄 Estado combinado actualizado para CP_001: available → offline (Monitor_KO (Engine: OK))
     ```
   - En dashboard: CP_001 debe aparecer como **Gris** (`offline`)

4. **Si hay sesión activa:**
   - Central debe finalizar automáticamente la sesión
   - En logs:
     ```
     [CENTRAL] ✅ Sesión X finalizada por Monitor KO para usuario driver1
     ```

**Resultado esperado:** CP_001 aparece como `offline` (Gris) en Central, incluso si Engine sigue funcionando.

---

### **Prueba 4: Estados Combinados - Monitor_KO + Engine_KO**

**Objetivo:** Verificar que cuando ambos están KO, el CP está `offline`.

**Pasos:**
1. Detener tanto el Monitor como el Engine (Ctrl+C en ambos).

2. **Esperar 30 segundos**.

3. **Verificar en Central:**
   - En logs:
     ```
     [CENTRAL] 🚨 Monitor KO detectado para CP_001 (sin heartbeat por 35.2s)
     [CENTRAL] 🔄 Estado combinado actualizado para CP_001: fault → offline (Monitor_KO (Engine: UNKNOWN))
     ```
   - En dashboard: CP_001 debe aparecer como **Gris** (`offline`)

**Resultado esperado:** CP_001 aparece como `offline` (Gris) en Central.

---

### **Prueba 5: Monitor se Desconecta (Ctrl+C)**

**Objetivo:** Verificar que Central detecta cuando Monitor se cae y marca CP como "Desconectado".

**Pasos:**
1. Iniciar Central, Engine (CP_001) y Monitor para CP_001.

2. Iniciar una carga en CP_001:
   - Desde Driver, solicitar carga en CP_001
   - Esperar a que la carga esté en progreso

3. **Detener el Monitor** (Ctrl+C en la terminal del Monitor).

4. **Esperar 30 segundos** (timeout de heartbeat).

5. **Verificar en Central:**
   - En logs:
     ```
     [CENTRAL] 🚨 Monitor KO detectado para CP_001 (sin heartbeat por 35.2s)
     [CENTRAL] ✅ Sesión X finalizada por Monitor KO para usuario driver1
     ```
   - La sesión debe finalizarse automáticamente
   - CP_001 debe marcarse como `offline`

6. **Verificar que no se pueden iniciar nuevas cargas:**
   - Intentar solicitar carga en CP_001 desde Driver
   - Debe rechazarse (CP está `offline`)

**Resultado esperado:** 
- CP se marca como `offline` tras 30 segundos sin heartbeat
- Sesión activa se finaliza automáticamente
- No se pueden iniciar nuevas cargas

---

### **Prueba 6: Engine se Cae (Ctrl+C)**

**Objetivo:** Verificar que Monitor detecta fallo del Engine y Central marca como "Averiado".

**Pasos:**
1. Iniciar Central, Engine (CP_001) y Monitor para CP_001.

2. Iniciar una carga en CP_001.

3. **Detener el Engine** (Ctrl+C en la terminal del Engine).

4. **Verificar en Monitor:**
   - En logs (cada 1 segundo):
     ```
     [MONITOR-CP_001] ❌ Cannot connect to Engine (failure 1/3)
     [MONITOR-CP_001] ❌ Cannot connect to Engine (failure 2/3)
     [MONITOR-CP_001] ❌ Cannot connect to Engine (failure 3/3)
     [MONITOR-CP_001] 🚨 Engine offline, reporting to Central
     [MONITOR-CP_001] 📤 ENGINE_OFFLINE reported to Central
     ```

5. **Verificar en Central:**
   - En logs:
     ```
     [CENTRAL] 🚨 ENGINE_FAILURE recibido: cp=CP_001, type=timeout
     [CENTRAL] ✅ CP CP_001 marcado como fault (era available)
     [CENTRAL] ✅ Sesión X cancelada por ENGINE_FAILURE para usuario driver1
     ```
   - La sesión debe cancelarse
   - CP debe marcarse como `fault` (Rojo)

6. **Verificar notificación al Driver:**
   - El Driver debe recibir un mensaje de error
   - En logs del Driver:
     ```
     [DRIVER] 🚨 Error en CP_001: El punto de carga CP_001 no responde. La carga ha sido cancelada.
     ```

**Resultado esperado:**
- Monitor detecta fallo en 3 segundos
- Central marca CP como `fault`
- Sesión se cancela
- Driver es notificado

---

### **Prueba 7: Engine Recupera Sesión Tras Crash**

**Objetivo:** Verificar que Engine guarda datos de sesión y los envía a Central al recuperarse.

**Pasos:**
1. Iniciar Central, Engine (CP_001) y Monitor.

2. Iniciar una carga en CP_001:
   - Desde Driver, solicitar carga
   - Esperar 10-15 segundos para que se acumule energía

3. **Detener el Engine abruptamente** (Ctrl+C o cerrar terminal).

4. **Verificar que se guardó archivo de sesión:**
   ```bash
   ls -la cp_CP_001_session.json
   # O en /tmp/cp_CP_001_session.json (Linux)
   ```

5. **Reiniciar el Engine:**
   ```bash
   python EV_CP_E.py --cp-id CP_001 --location "Test Location"
   ```

6. **Verificar en logs del Engine:**
   ```
   [CP_001] 🔄 Recuperando sesión tras crash:
   [CP_001]    Usuario: driver1
   [CP_001]    Energía: X.XX kWh
   [CP_001]    Coste: €X.XX
   [CP_001] 📤 Estado final enviado a Central
   ```

7. **Verificar en Central:**
   - En logs:
     ```
     [CENTRAL] 📨 charging_completed recibido: cp=CP_001, reason=engine_recovered
     ```
   - La sesión debe finalizarse con la energía correcta

**Resultado esperado:**
- Engine guarda sesión periódicamente
- Al recuperarse, envía estado final a Central
- Central procesa el evento y finaliza la sesión correctamente

---

### **Prueba 8: Driver se Cierra Durante Carga**

**Objetivo:** Verificar que la carga continúa aunque el Driver se desconecte.

**Pasos:**
1. Iniciar Central, Engine (CP_001), Monitor y Driver.

2. Iniciar una carga desde Driver:
   - Solicitar carga en CP_001
   - Esperar a que la carga esté en progreso (ver energía acumulándose)

3. **Cerrar el Driver** (Ctrl+C o cerrar navegador).

4. **Verificar que la carga continúa:**
   - En logs del Engine:
     ```
     [CP_001] 📤 Published event: charging_progress
        Energy: X.XX kWh | Cost: €X.XX
     ```
   - Los eventos `charging_progress` deben seguir publicándose cada segundo

5. **Esperar 30 segundos** (la carga continúa).

6. **Reabrir el Driver** y reconectarse:
   - Al iniciar sesión, el Driver debe consultar Central
   - Si la carga aún está activa, debe mostrar el estado actual

**Resultado esperado:**
- La carga continúa aunque el Driver esté desconectado
- Al reconectarse, el Driver puede ver el estado actual (si está implementada la recuperación)

---

### **Prueba 9: Central se Cae Durante Carga**

**Objetivo:** Verificar que los CPs continúan cargando aunque Central esté down.

**Pasos:**
1. Iniciar Central, Engine (CP_001), Monitor y Driver.

2. Iniciar una carga en CP_001.

3. **Detener Central** (Ctrl+C en la terminal de Central).

4. **Verificar que la carga continúa:**
   - En logs del Engine:
     ```
     [CP_001] 📤 Published event: charging_progress
        Energy: X.XX kWh | Cost: €X.XX
     ```
   - Los eventos `charging_progress` deben seguir publicándose
   - La carga debe continuar hasta que se detenga manualmente

5. **Intentar iniciar nueva carga:**
   - Desde Driver, intentar solicitar carga en otro CP
   - Debe fallar (Central no está disponible para autorizar)

6. **Reiniciar Central:**
   ```bash
   python EV_Central_WebSocket.py
   ```

7. **Cuando la carga actual termine:**
   - El Engine intentará enviar el evento `charging_completed` a Central
   - Si Central está disponible, lo procesará
   - Si Central sigue down, el evento puede perderse (limitación actual)

**Resultado esperado:**
- La carga actual continúa aunque Central esté down
- No se pueden iniciar nuevas cargas (requiere autorización de Central)
- Al reiniciar Central, puede procesar eventos pendientes (si Kafka los retiene)

---

## 📊 Verificación de Logs

### **Logs Clave a Buscar:**

1. **Heartbeats del Monitor:**
   ```
   [MONITOR-CP_XXX] 💓 Heartbeat sent to Central (Engine: OK/KO)
   ```

2. **Detección de Monitor KO:**
   ```
   [CENTRAL] 🚨 Monitor KO detectado para CP_XXX (sin heartbeat por X.Xs)
   ```

3. **Estados Combinados:**
   ```
   [CENTRAL] 🔄 Estado combinado actualizado para CP_XXX: estado_anterior → estado_nuevo (razón)
   ```

4. **Engine OK:**
   ```
   [MONITOR-CP_XXX] 📤 ENGINE_OK reported to Central (recovered)
   [CENTRAL] ✅ ENGINE_OK recibido: cp=CP_XXX - Engine recuperado
   ```

5. **Engine FAILURE:**
   ```
   [MONITOR-CP_XXX] 📤 ENGINE_FAILURE reported to Central
   [CENTRAL] 🚨 ENGINE_FAILURE recibido: cp=CP_XXX
   ```

6. **Recuperación de Sesión:**
   ```
   [CP_XXX] 🔄 Recuperando sesión tras crash:
   [CP_XXX] 📤 Estado final enviado a Central
   ```

---

## ✅ Checklist de Verificación

- [ ] **Estados Combinados:**
  - [ ] Monitor_OK + Engine_OK → `available`
  - [ ] Monitor_OK + Engine_KO → `fault`
  - [ ] Monitor_KO + Engine_OK → `offline`
  - [ ] Monitor_KO + Engine_KO → `offline`

- [ ] **Manejo de Fallos:**
  - [ ] Monitor se desconecta → CP marcado como `offline`, sesión finalizada
  - [ ] Engine se cae → Monitor detecta, Central marca como `fault`, Driver notificado
  - [ ] Driver se cierra → Carga continúa
  - [ ] Engine recupera sesión tras crash → Envía estado final a Central
  - [ ] Central se cae → CPs continúan cargando, no se aceptan nuevas cargas

---

## 🐛 Troubleshooting

### **Los heartbeats no aparecen:**
- Verificar que el Monitor está enviando eventos a Kafka
- Verificar conectividad Kafka entre Monitor y Central
- Revisar logs del Monitor para errores de Kafka

### **Central no detecta Monitor KO:**
- Verificar que `check_monitor_timeouts()` está corriendo
- Verificar que hay heartbeats registrados en `shared_state.monitor_heartbeats`
- Aumentar timeout si es necesario (actualmente 30 segundos)

### **Engine no recupera sesión:**
- Verificar que existe archivo `cp_CP_XXX_session.json`
- Verificar permisos de escritura en el directorio
- Revisar logs del Engine al iniciar

### **Estados combinados no se aplican:**
- Verificar que `update_combined_status()` se llama
- Verificar que `monitor_status` y `engine_status` están actualizados
- Revisar logs de Central para ver qué estados se están combinando

---

## 📝 Notas

1. **Heartbeats:** El Monitor envía heartbeats cada 10 segundos. Central verifica cada 15 segundos si hay heartbeats en los últimos 30 segundos.

2. **Persistencia:** El Engine guarda la sesión cada 5 segundos en un archivo JSON local. Al recuperarse, calcula la energía final y la envía a Central.

3. **Timeouts:** 
   - Monitor heartbeat timeout: 30 segundos
   - Engine health check: cada 1 segundo, reporta tras 3 fallos consecutivos

4. **Limitaciones Actuales:**
   - Si Central está down cuando Engine termina carga, el evento puede perderse (requiere buffer de eventos pendiente)
   - Driver no consulta sesión pendiente automáticamente al reconectarse (requiere implementación adicional)

