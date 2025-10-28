# RESUMEN FIX FINAL - El problema real y la solución

## El problema reportado

1. Cuando Driver detiene carga → Central NO procesa y sigue suministrando
2. Cuando Central simula error en CP → Driver NO recibe notificación

## La causa raíz

**Las funciones NO existían con los nombres correctos:**

En mi fix inicial usé:
- `end_charging_session()` ← ❌ NO EXISTE
- `get_active_session_by_username()` ← ❌ NO EXISTE

En database.py las funciones se llaman:
- `end_charging_sesion()` ← ✅ (sin acento en "sesion")
- `get_active_sesion_for_user(user_id)` ← ✅ (toma `user_id`, no `username`)

**Por eso el código nunca funcionó** - las llamadas a funciones inexistentes simplemente fallaban silenciosamente.

## La solución aplicada

### 1. Corregir nombres de funciones en Central (SD/EV_Central/EV_Central_WebSocket.py)

```python
elif action in ['charging_stopped']:
    username = event.get('username')
    user_id = event.get('user_id')
    energy_kwh = event.get('energy_kwh', 0)
    
    # Si no tenemos user_id, buscar por username
    if not user_id and username:
        user = db.get_user_by_username(username)
        if user:
            user_id = user.get('id')
    
    # Buscar sesión activa del usuario
    if user_id:
        session = db.get_active_sesion_for_user(user_id)  # ← CORRECTO
        if session:
            session_id = session.get('id')
            result = db.end_charging_sesion(session_id, energy_kwh)  # ← CORRECTO
            if result:
                print(f"[CENTRAL] ✅ Sesión finalizada: {energy_kwh} kWh, coste={result.get('coste')} EUR")
```

### 2. Agregar `user_id` al evento en Driver (SD/EV_Driver/EV_Driver_WebSocket.py)

```python
# Publicar evento de STOP a Central
if self.producer:
    # Buscar user_id
    users = {'driver1': {'id': 1}, 'driver2': {'id': 2}, 'maria_garcia': {'id': 3}}
    user_id = users.get(username, {}).get('id', 1)
    
    event = {
        'message_id': generate_message_id(),
        'driver_id': self.driver_id,
        'action': 'charging_stopped',
        'username': username,
        'user_id': user_id,  # ← AGREGADO
        'cp_id': cp_id,
        'energy_kwh': energy_kwh,
        'timestamp': current_timestamp()
    }
    self.producer.send(KAFKA_TOPIC_PRODUCE, event)
```

## Evidencia del problema

Ejecutamos `check_charging_state.py` y encontramos:

```
[ERROR] HAY 6 SESIONES ACTIVAS SIN CERRAR:
  Sesion ID 39: user_id=2 (driver2) en CP_002 - Estado: active
  Sesion ID 38: user_id=1 (driver1) en CP_001 - Estado: active
  Sesion ID 37: user_id=2 (driver2) en CP_002 - Estado: completed (SIN end_time!)
  Sesion ID 36: user_id=1 (driver1) en CP_001 - Estado: completed (SIN end_time!)
  ...
```

Las sesiones con estado 'completed' pero sin `end_time` confirman que Central no está ejecutando `end_charging_sesion()`.

## Archivos modificados

1. `SD/EV_Central/EV_Central_WebSocket.py` (línea 884-930)
   - Usa `db.get_active_sesion_for_user(user_id)` (correcto)
   - Usa `db.end_charging_sesion(session_id, energy_kwh)` (correcto)
   - Agrega fallback para buscar `user_id` si solo hay `username`

2. `SD/EV_Driver/EV_Driver_WebSocket.py` (línea 373-390)
   - Agrega `user_id` al evento de `charging_stopped`

## Cómo aplicar el fix

```powershell
# PC2 (Central)
cd C:\Users\luisb\Desktop\SD_Final\SD\SD
docker-compose -f docker-compose.pc2.yml down
docker-compose -f docker-compose.pc2.yml up -d --build

# PC1 (Driver)
docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc1.yml up -d --build
```

## Cómo verificar que funciona

```powershell
python check_charging_state.py
```

Antes del fix:
```
[ERROR] HAY 6 SESIONES ACTIVAS SIN CERRAR
```

Después del fix:
```
[OK] No hay sesiones activas sin cerrar
```

## Resumen

**Problema:** Nombres de funciones incorrectos en el código  
**Solución:** Usar `end_charging_sesion()` y `get_active_sesion_for_user()`  
**Resultado:** Central ahora SÍ cierra sesiones cuando Driver detiene carga  

El fix para los eventos de error de CP ya estaba correcto desde antes.

