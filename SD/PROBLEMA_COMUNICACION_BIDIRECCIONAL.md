# 🔴 PROBLEMAS DE COMUNICACIÓN BIDIRECCIONAL

## 🐛 Problema 1: Driver detiene carga → Central no procesa correctamente

### Situación Actual

```
Driver: User pulsa "Detener Carga"
  ↓
Driver envía a Kafka (driver-events):
  {
    action: 'charging_stopped',
    username: 'driver1',
    cp_id: 'CP_001'
  }
  ↓
Central consume el evento ✅
  ↓
Central ejecuta (línea 867-872):
  db.release_charging_point(cp_id, 'available') ✅
  ↓
Central NO cierra la sesión en BD ❌
Central NO termina el suministro ❌
```

### Código Actual (EV_Central_WebSocket.py línea 867-872)

```python
elif action in ['charging_stopped']:
    # Marcar CP disponible cuando termina el suministro
    if db.release_charging_point(cp_id, 'available'):
        print(f"[CENTRAL] ✅ Suministro finalizado - CP {cp_id} ahora disponible")
    else:
        print(f"[CENTRAL] ⚠️ Error liberando CP {cp_id} tras fin de carga")
```

### Problema

1. ✅ Central SÍ recibe el evento `charging_stopped`
2. ✅ Central libera el CP (lo marca como `available`)
3. ❌ Central NO cierra la sesión activa en la BD
4. ❌ Central NO calcula el costo/energía de la sesión
5. ❌ Central NO actualiza el balance del usuario

**Resultado:** El CP queda disponible pero la sesión sigue activa en la BD.

---

## 🐛 Problema 2: Central simula error → Driver no recibe notificación

### Situación Actual

```
Admin (Central Dashboard): Simula error en CP_001
  ↓
Central recibe via WebSocket (línea 383-403)
  ↓
Central actualiza BD:
  db.update_charging_point_status(cp_id, 'fault') ✅
  ↓
Central envía confirmación a Admin via WebSocket ✅
  ↓
Central hace broadcast a otros clientes ADMIN ✅
  ↓
Central NO publica en Kafka ❌
  ↓
Driver NO se entera del error ❌
```

### Código Actual (EV_Central_WebSocket.py línea 383-415)

```python
elif msg_type == 'simulate_error':
    # Simular error en un punto de carga
    cp_id = data.get('cp_id')
    error_type = data.get('error_type')
    
    # Mapear tipo de error a estado
    status_map = {
        'fault': 'fault',
        'out_of_service': 'out_of_service',
        'offline': 'offline'
    }
    new_status = status_map.get(error_type, 'fault')
    
    # Actualizar estado en BD
    db.update_charging_point_status(cp_id, new_status)  ✅
    
    # Enviar confirmación
    await ws.send_str(json.dumps({
        'type': 'error_simulated',
        'message': f'Error "{error_type}" simulado en {cp_id}'
    }))  ✅
    
    # Broadcast a todos los clientes ADMIN (WebSocket)
    for client in shared_state.connected_clients:
        if client != ws:
            try:
                await client.send_str(json.dumps({
                    'type': 'all_cps',
                    'charging_points': cps
                }))  ✅
            except:
                pass
    
    # ❌ NO publica en Kafka
    # ❌ Driver nunca se entera
```

### Problema

1. ✅ Central actualiza el estado del CP en la BD
2. ✅ Central notifica a dashboards de Admin
3. ❌ Central NO publica evento en topic `central-events`
4. ❌ Driver NO consume el evento
5. ❌ Driver NO notifica al usuario que su CP tiene un error
6. ❌ Si el usuario estaba cargando, sigue mostrando "CARGANDO" aunque el CP esté en fault

**Resultado:** El Driver no se entera cuando un CP tiene un error simulado.

---

## ✅ SOLUCIONES

### Solución 1: Central debe procesar correctamente `charging_stopped`

**Archivo:** `SD/EV_Central/EV_Central_WebSocket.py` (línea 867-872)

**ANTES:**
```python
elif action in ['charging_stopped']:
    # Marcar CP disponible cuando termina el suministro
    if db.release_charging_point(cp_id, 'available'):
        print(f"[CENTRAL] ✅ Suministro finalizado - CP {cp_id} ahora disponible")
    else:
        print(f"[CENTRAL] ⚠️ Error liberando CP {cp_id} tras fin de carga")
```

**AHORA:**
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
                print(f"[CENTRAL] ✅ Sesión {session_id} finalizada en BD")
            
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

**Beneficios:**
- ✅ Cierra la sesión en BD
- ✅ Calcula el costo final
- ✅ Actualiza el balance del usuario
- ✅ Libera el CP para otro usuario

---

### Solución 2: Central debe publicar eventos de error en Kafka

**Archivo:** `SD/EV_Central/EV_Central_WebSocket.py` (línea 383-415)

**CAMBIO: Agregar publicación en Kafka después de actualizar BD**

```python
elif msg_type == 'simulate_error':
    # Simular error en un punto de carga
    cp_id = data.get('cp_id')
    error_type = data.get('error_type')
    
    # Mapear tipo de error a estado
    status_map = {
        'fault': 'fault',
        'out_of_service': 'out_of_service',
        'offline': 'offline'
    }
    new_status = status_map.get(error_type, 'fault')
    
    # Actualizar estado en BD
    db.update_charging_point_status(cp_id, new_status)
    
    # 🆕 PUBLICAR EVENTO EN KAFKA para notificar al Driver
    central_instance.publish_event('CP_ERROR_SIMULATED', {
        'cp_id': cp_id,
        'error_type': error_type,
        'new_status': new_status,
        'message': f'Error "{error_type}" simulado en {cp_id}'
    })
    
    # Enviar confirmación al admin
    await ws.send_str(json.dumps({
        'type': 'error_simulated',
        'message': f'Error "{error_type}" simulado en {cp_id}'
    }))
    
    # Broadcast a todos los clientes admin
    cps = [central_instance._standardize_cp(cp) for cp in (db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else [])]
    for client in shared_state.connected_clients:
        if client != ws:
            try:
                await client.send_str(json.dumps({
                    'type': 'all_cps',
                    'charging_points': cps
                }))
            except:
                pass
```

**CAMBIO SIMILAR para `fix_error`:**

```python
elif msg_type == 'fix_error':
    # Corregir error en un punto de carga
    cp_id = data.get('cp_id')
    
    # Cambiar estado a available
    db.update_charging_point_status(cp_id, 'available')
    
    # 🆕 PUBLICAR EVENTO EN KAFKA para notificar al Driver
    central_instance.publish_event('CP_ERROR_FIXED', {
        'cp_id': cp_id,
        'new_status': 'available',
        'message': f'Error corregido en {cp_id}'
    })
    
    # Enviar confirmación al admin
    await ws.send_str(json.dumps({
        'type': 'error_fixed',
        'message': f'Error corregido en {cp_id}'
    }))
    
    # Broadcast a todos los clientes admin
    # ... (resto del código)
```

**Beneficios:**
- ✅ Driver recibe notificación vía Kafka
- ✅ Driver puede informar al usuario del error
- ✅ Driver puede detener la carga si estaba activa en ese CP

---

### Solución 3: Driver debe procesar eventos de error del Central

**Archivo:** `SD/EV_Driver/EV_Driver_WebSocket.py`

Necesitamos agregar un listener de Kafka que procese los eventos `CP_ERROR_SIMULATED` y `CP_ERROR_FIXED` del topic `central-events`.

**Agregar en el kafka_listener:**

```python
def kafka_listener(driver):
    """Escucha eventos de Kafka en un thread separado"""
    print(f"[KAFKA] 🎧 Iniciando listener en topic: {KAFKA_TOPICS_CONSUME}")
    
    # ... código existente ...
    
    for message in consumer:
        try:
            event = message.value
            event_type = event.get('event_type')
            
            # ... código existente para AUTHORIZATION_RESPONSE ...
            
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
        
        except Exception as e:
            print(f"[KAFKA] Error processing message: {e}")
```

**Y en el process_notifications agregar los nuevos tipos:**

```python
async def process_notifications():
    """Procesa notificaciones desde la cola y las envía a los websockets"""
    while True:
        try:
            notification = shared_state.notification_queue.get_nowait()
            
            # ... código existente ...
            
            # 🆕 NOTIFICACIONES DE ERROR DE CP
            elif notification['type'] == 'cp_error':
                username = notification.get('username')
                cp_id = notification['cp_id']
                message_text = notification['message']
                
                message = json.dumps({
                    'type': 'cp_error',
                    'cp_id': cp_id,
                    'message': message_text
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
                    except:
                        pass
        
        except Exception as e:
            await asyncio.sleep(0.1)
```

**Y en dashboard.html agregar handlers:**

```javascript
case 'cp_error':
    // Si el usuario está cargando en este CP, mostrar error
    if (sessionData.cp_id === data.cp_id) {
        document.getElementById('chargingStatus').textContent = '❌ ERROR EN CP';
        addEvent(`⚠️ ${data.message}`);
        alert(`Error en tu punto de carga: ${data.message}`);
    }
    break;

case 'cp_fixed':
    addEvent(`✅ ${data.message}`);
    break;
```

---

## 📊 FLUJO DESPUÉS DE LOS FIXES

### Flujo 1: Driver detiene carga

```
Driver: "Detener Carga"
  ↓
Driver → Kafka (driver-events): charging_stopped
  ↓
Central consume ✅
  ↓
Central:
  1. Busca sesión activa del usuario ✅
  2. Finaliza sesión en BD ✅
  3. Calcula costo/energía ✅
  4. Actualiza balance usuario ✅
  5. Libera CP → 'available' ✅
  ↓
Driver:
  - Muestra "Carga completada"
  - Balance actualizado
```

### Flujo 2: Central simula error

```
Admin: "Simular error en CP_001"
  ↓
Central recibe via WebSocket
  ↓
Central:
  1. Actualiza BD: CP_001 → 'fault' ✅
  2. Publica en Kafka (central-events): CP_ERROR_SIMULATED ✅
  3. Notifica a Admin dashboard ✅
  ↓
Driver consume de Kafka ✅
  ↓
Driver:
  1. Verifica si algún usuario usa CP_001 ✅
  2. Si sí: Notifica al usuario ✅
  3. Muestra "❌ ERROR EN CP" ✅
```

---

## 🎯 RESUMEN

| Problema | Causa | Solución |
|----------|-------|----------|
| Central no termina sesión al detener carga | Solo libera CP, no cierra sesión en BD | Agregar `db.end_charging_session()` |
| Driver no recibe errores de CP | Central no publica en Kafka | Agregar `publish_event()` en simulate_error |
| Driver no puede reaccionar a errores | No hay listener para eventos de error | Agregar handler en kafka_listener |

¿Quieres que aplique estos fixes ahora?

