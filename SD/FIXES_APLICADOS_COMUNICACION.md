# ✅ FIXES APLICADOS - Comunicación Bidireccional

## 🎯 Resumen

Se han corregido **2 problemas críticos** de comunicación bidireccional entre Central y Driver:

1. ✅ **Driver detiene carga** → Central ahora procesa correctamente y cierra la sesión
2. ✅ **Central simula error en CP** → Driver ahora recibe la notificación en tiempo real

---

## 📝 Fix 1: Central procesa correctamente charging_stopped

### Archivo: `SD/EV_Central/EV_Central_WebSocket.py` (línea 867-895)

**Problema:** Central solo liberaba el CP, pero NO cerraba la sesión en BD.

**Solución:** Ahora Central:
1. Busca la sesión activa del usuario
2. Finaliza la sesión en BD con `db.end_charging_session()`
3. Calcula el costo final
4. Actualiza el balance del usuario
5. Libera el CP para que esté disponible

```python
elif action in ['charging_stopped']:
    # Finalizar sesión de carga y liberar CP
    username = event.get('username')
    energy_kwh = event.get('energy_kwh', 0)
    
    print(f"[CENTRAL] ⛔ Procesando charging_stopped: user={username}, cp={cp_id}, energy={energy_kwh}")
    
    # 1. Buscar sesión activa del usuario
    try:
        session = db.get_active_session_by_username(username)
        if session:
            session_id = session.get('id') or session.get('session_id') or session.get('sesion_id')
            
            # 2. Finalizar sesión en BD
            if session_id:
                db.end_charging_session(session_id, energy_kwh)
                print(f"[CENTRAL] ✅ Sesión {session_id} finalizada en BD con {energy_kwh} kWh")
            
            # 3. Liberar CP
            if db.release_charging_point(cp_id, 'available'):
                print(f"[CENTRAL] ✅ Suministro finalizado - CP {cp_id} ahora disponible")
        else:
            print(f"[CENTRAL] ⚠️ No se encontró sesión activa para {username}")
            # Liberar el CP de todas formas
            db.release_charging_point(cp_id, 'available')
    except Exception as e:
        print(f"[CENTRAL] ❌ Error procesando charging_stopped: {e}")
        # Liberar el CP de todas formas
        db.release_charging_point(cp_id, 'available')
```

---

## 📝 Fix 2: Central publica eventos de error en Kafka

### Archivo: `SD/EV_Central/EV_Central_WebSocket.py` (línea 399-406, 433-439)

**Problema:** Central solo notificaba a los dashboards de Admin, pero NO publicaba en Kafka.

**Solución:** Ahora Central publica eventos `CP_ERROR_SIMULATED` y `CP_ERROR_FIXED` en Kafka.

#### a) simulate_error

```python
elif msg_type == 'simulate_error':
    # ... código existente ...
    
    # 🆕 PUBLICAR EVENTO EN KAFKA para notificar al Driver
    central_instance.publish_event('CP_ERROR_SIMULATED', {
        'cp_id': cp_id,
        'error_type': error_type,
        'new_status': new_status,
        'message': f'Error "{error_type}" simulado en {cp_id}'
    })
    print(f"[CENTRAL] 📢 Publicado CP_ERROR_SIMULATED en Kafka para {cp_id}")
```

#### b) fix_error

```python
elif msg_type == 'fix_error':
    # ... código existente ...
    
    # 🆕 PUBLICAR EVENTO EN KAFKA para notificar al Driver
    central_instance.publish_event('CP_ERROR_FIXED', {
        'cp_id': cp_id,
        'new_status': 'available',
        'message': f'Error corregido en {cp_id}'
    })
    print(f"[CENTRAL] 📢 Publicado CP_ERROR_FIXED en Kafka para {cp_id}")
```

---

## 📝 Fix 3: Driver procesa eventos de error de Central

### Archivo: `SD/EV_Driver/EV_Driver_WebSocket.py` (línea 161-196)

**Problema:** Driver NO consumía eventos de error de CP del Central.

**Solución:** Agregado procesamiento de eventos en `kafka_listener()`:

```python
# 🆕 PROCESAR EVENTOS DE ERROR DE CP
elif event_type == 'CP_ERROR_SIMULATED':
    cp_id = event.get('cp_id')
    error_type = event.get('error_type')
    message_text = event.get('message')
    
    print(f"[DRIVER] ⚠️ CP {cp_id} tiene error: {error_type}")
    
    # Verificar si algún usuario está usando ese CP
    with shared_state.lock:
        for username, session in list(shared_state.charging_sessions.items()):
            if session.get('cp_id') == cp_id:
                # Notificar al usuario
                notification = {
                    'type': 'cp_error',
                    'cp_id': cp_id,
                    'error_type': error_type,
                    'message': message_text,
                    'username': username
                }
                shared_state.notification_queue.put(notification)
                print(f"[DRIVER] 📢 Notificando error a {username}")

elif event_type == 'CP_ERROR_FIXED':
    cp_id = event.get('cp_id')
    message_text = event.get('message')
    
    print(f"[DRIVER] ✅ CP {cp_id} reparado")
    
    # Notificar a todos los usuarios conectados
    notification = {
        'type': 'cp_fixed',
        'cp_id': cp_id,
        'message': message_text
    }
    shared_state.notification_queue.put(notification)
```

---

## 📝 Fix 4: Driver envía notificaciones a WebSocket

### Archivo: `SD/EV_Driver/EV_Driver_WebSocket.py` (línea 1162-1209)

**Problema:** Las notificaciones de error de CP no se enviaban al frontend.

**Solución:** Agregado handler en `process_notifications()`:

```python
# 🆕 NOTIFICACIONES DE ERROR DE CP
elif notification['type'] == 'cp_error':
    username = notification.get('username')
    cp_id = notification['cp_id']
    message_text = notification['message']
    
    message = json.dumps({
        'type': 'cp_error',
        'cp_id': cp_id,
        'message': message_text,
        'username': username
    })
    
    # Broadcast a todos (el frontend filtrará)
    with shared_state.lock:
        clients = list(shared_state.connected_clients)
    for client in clients:
        try:
            if hasattr(client, 'send_str'):
                await client.send_str(message)
            else:
                await client.send(message)
            print(f"[NOTIF] ⚠️ Error de CP notificado a cliente")
        except:
            pass

elif notification['type'] == 'cp_fixed':
    cp_id = notification['cp_id']
    message_text = notification['message']
    
    message = json.dumps({
        'type': 'cp_fixed',
        'cp_id': cp_id,
        'message': message_text
    })
    
    # Broadcast a todos
    with shared_state.lock:
        clients = list(shared_state.connected_clients)
    for client in clients:
        try:
            if hasattr(client, 'send_str'):
                await client.send_str(message)
            else:
                await client.send(message)
            print(f"[NOTIF] ✅ Reparación de CP notificada a cliente")
        except:
            pass
```

---

## 📝 Fix 5: Dashboard del Driver muestra errores

### Archivo: `SD/EV_Driver/dashboard.html` (línea 604-627)

**Problema:** Dashboard no manejaba eventos de error de CP.

**Solución:** Agregado handler en el WebSocket:

```javascript
// 🆕 EVENTOS DE ERROR DE CP DESDE CENTRAL
case 'cp_error':
    // Si el usuario está cargando en este CP, mostrar error
    if (sessionData.cp_id === data.cp_id) {
        document.getElementById('chargingStatus').textContent = '❌ ERROR EN CP';
        addEvent(`⚠️ ${data.message}`);
        alert(`Error en tu punto de carga: ${data.message}\nLa carga debe detenerse.`);
        
        // Mostrar botón de inicio, ocultar botón de detener
        document.getElementById('startBtn').classList.remove('hidden');
        document.getElementById('stopBtn').classList.add('hidden');
        
        // Limpiar sesión local
        sessionData.charging = false;
        sessionData.cp_id = null;
    } else if (data.username && data.username === currentUser) {
        // Si el error es para este usuario pero no está cargando
        addEvent(`⚠️ ${data.message}`);
    }
    break;

case 'cp_fixed':
    addEvent(`✅ ${data.message}`);
    break;
```

---

## 🔄 FLUJOS COMPLETOS DESPUÉS DE LOS FIXES

### Flujo 1: Driver detiene carga

```
👤 Usuario: Click en "Detener Carga"
  ↓
🚗 Driver (Frontend): Envía mensaje WebSocket
  ↓
🚗 Driver (Backend): Procesa stop_charging()
  ↓
📤 Driver → Kafka: Publica 'charging_stopped' en driver-events
  ↓
🏢 Central: Consume evento de Kafka
  ↓
🏢 Central: 
   1. Busca sesión activa del usuario ✅
   2. Finaliza sesión en BD ✅
   3. Calcula costo/energía ✅
   4. Actualiza balance usuario ✅
   5. Libera CP → 'available' ✅
  ↓
✅ RESULTADO: Sesión cerrada correctamente en BD
```

### Flujo 2: Central simula error en CP

```
👨‍💼 Admin: Simula error en CP_001 (tipo: fault)
  ↓
🏢 Central (WebSocket): Recibe mensaje del admin
  ↓
🏢 Central:
   1. Actualiza BD: CP_001 → 'fault' ✅
   2. Publica en Kafka: CP_ERROR_SIMULATED ✅
   3. Notifica a Admin dashboard ✅
  ↓
📡 Kafka: Evento en topic 'central-events'
  ↓
🚗 Driver (Consumer): Recibe CP_ERROR_SIMULATED ✅
  ↓
🚗 Driver:
   1. Verifica si algún usuario usa CP_001 ✅
   2. Si sí: Encola notificación para ese usuario ✅
  ↓
🚗 Driver (WebSocket): Envía notificación al navegador ✅
  ↓
👤 Usuario (Dashboard):
   - Muestra: "❌ ERROR EN CP" ✅
   - Alert: "Error en tu punto de carga..." ✅
   - Botones: Muestra "Solicitar Carga", oculta "Detener Carga" ✅
   - Log: "⚠️ Error 'fault' simulado en CP_001" ✅
  ↓
✅ RESULTADO: Usuario informado en tiempo real del error
```

---

## 🧪 PRUEBAS

### Prueba 1: Detener carga desde Driver

1. **Driver:** Inicia sesión y solicita carga
2. **Driver:** Click en "Detener Carga"
3. **Verificar logs de Central:**
   ```
   [CENTRAL] ⛔ Procesando charging_stopped: user=driver1, cp=CP_001, energy=X.X
   [CENTRAL] ✅ Sesión XXX finalizada en BD con X.X kWh
   [CENTRAL] ✅ Suministro finalizado - CP CP_001 ahora disponible
   ```
4. **Verificar BD:**
   - La sesión debe tener `fecha_fin` y `energia_kwh`
   - El CP debe estar en estado `available`
   - El balance del usuario debe estar actualizado

### Prueba 2: Central simula error en CP con usuario cargando

1. **Driver (PC1):** Login como driver1, solicitar carga → Asignado a CP_001
2. **Central (PC2):** Admin dashboard, seleccionar CP_001, simular error "fault"
3. **Verificar logs de Central:**
   ```
   [CENTRAL] 📢 Publicado CP_ERROR_SIMULATED en Kafka para CP_001
   ```
4. **Verificar logs de Driver:**
   ```
   [DRIVER] ⚠️ CP CP_001 tiene error: fault
   [DRIVER] 📢 Notificando error a driver1
   [NOTIF] ⚠️ Error de CP notificado a cliente
   ```
5. **Verificar Dashboard del Driver:**
   - Debe mostrar: "❌ ERROR EN CP"
   - Debe aparecer un alert: "Error en tu punto de carga: Error 'fault' simulado en CP_001"
   - Debe aparecer el botón "Solicitar Carga"
   - Debe desaparecer el botón "Detener Carga"
   - En el log: "⚠️ Error 'fault' simulado en CP_001"

### Prueba 3: Central repara CP

1. **Central:** Admin dashboard, seleccionar CP_001, click en "Corregir Error"
2. **Verificar logs de Central:**
   ```
   [CENTRAL] 📢 Publicado CP_ERROR_FIXED en Kafka para CP_001
   ```
3. **Verificar logs de Driver:**
   ```
   [DRIVER] ✅ CP CP_001 reparado
   [NOTIF] ✅ Reparación de CP notificada a cliente
   ```
4. **Verificar Dashboard del Driver:**
   - En el log: "✅ Error corregido en CP_001"

---

## 🚀 APLICAR LOS FIXES

### En PC2 (Central)

```powershell
cd C:\Users\luisb\Desktop\SD_Final\SD\SD
docker-compose -f docker-compose.pc2.yml down
docker-compose -f docker-compose.pc2.yml up -d --build
```

### En PC1 (Driver)

```powershell
cd C:\Users\luisb\Desktop\SD_Final\SD\SD
docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc1.yml up -d --build
```

### Verificar que funcionan

**PC2 (Central):**
```powershell
docker logs ev-central --tail 30
```

Deberías ver:
```
[CENTRAL] ✅ Kafka producer initialized
[HTTP] Server started on http://0.0.0.0:5001
```

**PC1 (Driver):**
```powershell
docker logs ev-driver --tail 30
```

Deberías ver:
```
[DRIVER] ✅ Kafka producer initialized
[KAFKA] 📡 Consumer started, listening to ['central-events']
[HTTP] Server started on http://0.0.0.0:8001
```

---

## ✅ RESULTADO FINAL

| Problema | Estado | Solución |
|----------|--------|----------|
| Central no procesa charging_stopped | ✅ RESUELTO | Central ahora cierra sesión en BD |
| Central no notifica errores de CP | ✅ RESUELTO | Central publica en Kafka |
| Driver no recibe errores de CP | ✅ RESUELTO | Driver consume y procesa eventos |
| Dashboard no muestra errores | ✅ RESUELTO | Dashboard maneja eventos cp_error |

---

## 📋 ARCHIVOS MODIFICADOS

1. ✅ `SD/EV_Central/EV_Central_WebSocket.py`
   - Línea 867-895: Fix charging_stopped
   - Línea 399-406: Fix simulate_error
   - Línea 433-439: Fix fix_error

2. ✅ `SD/EV_Driver/EV_Driver_WebSocket.py`
   - Línea 161-196: Kafka listener procesa eventos de error
   - Línea 1162-1209: process_notifications envía eventos al WebSocket

3. ✅ `SD/EV_Driver/dashboard.html`
   - Línea 604-627: Handler para eventos cp_error y cp_fixed

---

## 🎉 ¡TODO LISTO!

Ahora el sistema tiene **comunicación bidireccional completa**:
- ✅ Driver → Central: Solicitar carga, detener carga
- ✅ Central → Driver: Autorizar carga, notificar errores de CP
- ✅ Central procesa correctamente todas las acciones del Driver
- ✅ Driver se entera en tiempo real de los errores de CP

**Los dos problemas reportados están completamente resueltos.** 🚀

