# 🔧 FIX: Problema de CP duplicado en múltiples usuarios

## 🐛 Problema Reportado

Cuando dos usuarios diferentes solicitan carga:
- Central asigna correctamente CPs diferentes (CP_001 y CP_002)
- Pero en la interfaz del Driver, **ambos usuarios ven el mismo nombre de CP**

## 🔍 Causa Raíz

### 1. Backend: Broadcast a todos los clientes

En `EV_Driver_WebSocket.py`, función `process_notifications()` (líneas 1064-1077):

```python
# Fallback: enviar a todos los clientes si no se envió
if not sent:
    for client in clients_to_notify:
        await client.send_str(message)  # ← Envía a TODOS
```

**Problema:** Si el `client_id` no se encuentra en `pending_authorizations`, el mensaje `charging_started` se envía a **TODOS** los clientes conectados, no solo al usuario correcto.

**Causas posibles del fallback:**
- Problema de sincronización
- `pending_authorizations` se limpió antes de tiempo
- Reconexión del WebSocket

### 2. Frontend: Sin filtrado por usuario

En `dashboard.html` (líneas 536-557):

```javascript
case 'charging_started':
    sessionData.charging = true;
    sessionData.cp_id = data.cp_id;
    document.getElementById('chargingPoint').textContent = data.cp_id;
    // ← NO verifica si es para el usuario actual
```

**Problema:** Cuando llega un evento `charging_started`, el frontend actualiza la interfaz sin verificar si el evento es para el usuario actual.

## ✅ Solución Aplicada

### 1. Backend: Mejorar logging

**Archivo:** `SD/EV_Driver/EV_Driver_WebSocket.py`

```python
# Fallback: enviar a todos los clientes si no se envió
if not sent:
    print(f"[NOTIF] ⚠️ WARNING: Usando BROADCAST a todos los clientes para {username}")
    with shared_state.lock:
        clients_to_notify = list(shared_state.connected_clients)
    for client in clients_to_notify:
        try:
            if hasattr(client, 'send_str'):
                await client.send_str(message)
            else:
                await client.send(message)
        except:
            pass
    print(f"[NOTIF] 📢 Broadcast enviado a {len(clients_to_notify)} clientes")
```

**Cambios:**
- Agregado logging cuando se usa el fallback de broadcast
- Esto ayuda a identificar cuándo y por qué se está haciendo broadcast

### 2. Backend: Incluir username en charging_stopped

**Archivo:** `SD/EV_Driver/EV_Driver_WebSocket.py` (línea 830-836)

```python
await ws.send_str(json.dumps({
    'type': 'charging_stopped',
    'username': username,  # ← AGREGADO para filtrado en frontend
    'energy': result['energy'],
    'total_cost': result['total_cost'],
    'new_balance': result['new_balance']
}))
```

### 3. Frontend: Filtrar eventos por usuario

**Archivo:** `SD/EV_Driver/dashboard.html`

#### a) Filtrar `charging_started` (líneas 536-557)

```javascript
case 'charging_started':
    // FILTRAR: Solo procesar si es para el usuario actual
    if (data.username && data.username !== currentUser) {
        console.log(`[WS] Ignorando charging_started de otro usuario: ${data.username}`);
        break;  // ← Ignora el evento si no es para este usuario
    }
    
    sessionData.charging = true;
    sessionData.cp_id = data.cp_id;
    document.getElementById('chargingStatus').textContent = 'CARGANDO ⚡';
    document.getElementById('chargingPoint').textContent = data.cp_id;
    // ...
```

#### b) Filtrar `charging_stopped` (líneas 575-592)

```javascript
case 'charging_stopped':
    // FILTRAR: Solo procesar si es para el usuario actual
    if (data.username && data.username !== currentUser) {
        console.log(`[WS] Ignorando charging_stopped de otro usuario: ${data.username}`);
        break;  // ← Ignora el evento si no es para este usuario
    }
    
    sessionData.charging = false;
    document.getElementById('chargingStatus').textContent = 'COMPLETADO ✓';
    // ...
```

## 📊 Comparación

### ANTES del Fix:

```
Usuario 1 solicita carga → Central asigna CP_001
  └─> Backend envía: { type: 'charging_started', username: 'user1', cp_id: 'CP_001' }
      └─> Fallback: Broadcast a TODOS los clientes
          ├─> Cliente User1: Muestra "CP_001" ✓
          └─> Cliente User2: Muestra "CP_001" ✗ (INCORRECTO)

Usuario 2 solicita carga → Central asigna CP_002
  └─> Backend envía: { type: 'charging_started', username: 'user2', cp_id: 'CP_002' }
      └─> Fallback: Broadcast a TODOS los clientes
          ├─> Cliente User1: Muestra "CP_002" ✗ (SOBRESCRIBE)
          └─> Cliente User2: Muestra "CP_002" ✓
```

**Resultado:** Ambos usuarios terminan viendo el mismo CP (el último que se procesó).

### DESPUÉS del Fix:

```
Usuario 1 solicita carga → Central asigna CP_001
  └─> Backend envía: { type: 'charging_started', username: 'user1', cp_id: 'CP_001' }
      └─> Fallback: Broadcast a TODOS los clientes
          ├─> Cliente User1: username='user1' == currentUser → Muestra "CP_001" ✓
          └─> Cliente User2: username='user1' != currentUser → IGNORA ✓

Usuario 2 solicita carga → Central asigna CP_002
  └─> Backend envía: { type: 'charging_started', username: 'user2', cp_id: 'CP_002' }
      └─> Fallback: Broadcast a TODOS los clientes
          ├─> Cliente User1: username='user2' != currentUser → IGNORA ✓
          └─> Cliente User2: username='user2' == currentUser → Muestra "CP_002" ✓
```

**Resultado:** Cada usuario ve solo su CP asignado.

## 🧪 Cómo Probar

### 1. Abrir dos navegadores/pestañas

```bash
# Navegador 1: http://localhost:8001
# Navegador 2: http://localhost:8001
```

### 2. Iniciar sesión con usuarios diferentes

```
Navegador 1: Login como "driver1" / "pass123"
Navegador 2: Login como "driver2" / "pass123"
```

### 3. Solicitar carga en ambos

```
Navegador 1: Click en "Solicitar Carga"
  └─> Debería ver: "Punto de Carga: CP_001"

Navegador 2: Click en "Solicitar Carga"
  └─> Debería ver: "Punto de Carga: CP_002"
```

### 4. Verificar que no se sobrescriben

```
Navegador 1: Debería seguir mostrando "CP_001"
Navegador 2: Debería seguir mostrando "CP_002"
```

### 5. Revisar logs del Driver

```powershell
docker logs ev-driver --tail 50
```

**Buscar:**
```
[NOTIF] ⚠️ WARNING: Usando BROADCAST a todos los clientes para user1
[NOTIF] 📢 Broadcast enviado a 2 clientes
```

**En consola del navegador (F12):**
```
[WS] Ignorando charging_started de otro usuario: driver1
[WS] Ignorando charging_stopped de otro usuario: driver2
```

## 🎯 Resumen

| Aspecto | Cambio |
|---------|--------|
| **Backend** | Agregado logging de broadcast + username en charging_stopped |
| **Frontend** | Agregado filtrado por username en charging_started y charging_stopped |
| **Comportamiento** | Ahora cada usuario ve solo SU CP asignado |
| **Compatibilidad** | Totalmente compatible con flujo existente |

## 📝 Notas

1. **El filtrado es en el cliente:** El backend sigue enviando a todos (fallback), pero ahora cada cliente ignora eventos que no son para él.

2. **¿Por qué no eliminar el broadcast?** Porque puede ser un fallback útil en casos de reconexión o pérdida de sincronización. El filtrado en cliente es más robusto.

3. **Eventos `charging_update`:** Ya tenían filtrado por username (línea 561), por eso funcionaban correctamente.

4. **Próxima mejora:** Investigar por qué se usa el fallback de broadcast y corregir la causa raíz en `pending_authorizations`.

## ✅ Aplicar el Fix

### Si el Driver está corriendo:

```powershell
cd SD
docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc1.yml up -d --build
```

### Verificar:

```powershell
docker logs ev-driver --tail 20
```

Deberías ver:
```
[HTTP] 🌐 Server started on http://0.0.0.0:8001
[KAFKA] ✅ Kafka consumer connected
```

Ahora abre el dashboard y prueba con dos usuarios. 🎉

