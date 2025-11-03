# Análisis del Monitoreo TCP: Monitor solicita estado del Engine

## Resumen del Flujo de Health Checks

### 1. Monitor → Engine (Health Check TCP)

#### ✅ Monitor solicita estado cada 1 segundo

**Ubicación**: `EV_CP_M/EV_CP_M_WebSocket.py`, función `tcp_health_check()`

**Implementación**:
```python
async def tcp_health_check():
    while True:
        await asyncio.sleep(1)  # ✅ CADA 1 SEGUNDO
        
        # Conectar al Engine
        reader, writer = await asyncio.open_connection(
            monitor_instance.engine_host, 
            monitor_instance.engine_port
        )
        
        # Enviar "STATUS?"
        writer.write(b"STATUS?\n")
        await writer.drain()
        
        # Esperar respuesta
        data = await reader.readuntil(b'\n')
        response = data.decode().strip()  # "OK" o "KO"
        
        # Procesar respuesta
        if response == "OK":
            consecutive_failures = 0
        elif response == "KO":
            consecutive_failures += 1
            if consecutive_failures >= 3:
                # Reportar a Central
                report_engine_failure_to_central()
```

**Frecuencia**: ✅ **CADA 1 SEGUNDO** (según especificación)

**Timeout de conexión**: 5.0 segundos
**Timeout de respuesta**: 5.0 segundos

**Estado**: ✅ **CORRECTO** - Monitor solicita estado cada segundo

---

### 2. Engine → Monitor (Respuesta TCP)

#### ✅ Engine responde a health checks

**Ubicación**: `EV_CP_E/EV_CP_E.py`, función `start_health_check_server()`

**Implementación**:
```python
def start_health_check_server(self):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', self.health_check_port))
    server_socket.listen(5)
    
    while self.running:
        client_socket, address = server_socket.accept()
        data = client_socket.recv(1024).decode('utf-8').strip()
        
        if data == "STATUS?":
            # Responder según estado
            with self.lock:
                if self.status == 'fault':
                    response = "KO"
                else:
                    response = self.health_status  # "OK" por defecto
            
            # Enviar respuesta
            client_socket.sendall((response + '\n').encode('utf-8'))
            client_socket.close()
```

**Respuestas**:
- ✅ **"OK"** - Si `status != 'fault'` y `health_status == 'OK'`
- ✅ **"KO"** - Si `status == 'fault'` o `health_status == 'KO'`

**Estado**: ✅ **CORRECTO** - Engine responde correctamente a health checks

---

## Flujo Completo Verificado

### Flujo Normal (Engine OK)

1. **Monitor** → Conecta al Engine cada 1 segundo
2. **Monitor** → Envía "STATUS?\n"
3. **Engine** → Recibe "STATUS?"
4. **Engine** → Responde "OK\n"
5. **Monitor** → Recibe "OK"
6. **Monitor** → Resetea `consecutive_failures = 0`
7. **Monitor** → Actualiza `shared_state.health_status` a `'OK'`

**Estado**: ✅ **FUNCIONA CORRECTAMENTE**

---

### Flujo con Fallo (Engine KO)

1. **Monitor** → Conecta al Engine cada 1 segundo
2. **Monitor** → Envía "STATUS?\n"
3. **Engine** → Recibe "STATUS?"
4. **Engine** → Responde "KO\n" (porque `status == 'fault'`)
5. **Monitor** → Recibe "KO"
6. **Monitor** → Incrementa `consecutive_failures += 1`
7. **Monitor** → Si `consecutive_failures >= 3`:
   - Reporta `ENGINE_FAILURE` a Central vía Kafka
   - Resetea `consecutive_failures = 0`
8. **Monitor** → Actualiza `shared_state.health_status` a `'KO'`

**Estado**: ✅ **FUNCIONA CORRECTAMENTE**

---

### Flujo con Timeout (Engine no responde)

1. **Monitor** → Intenta conectar al Engine
2. **Monitor** → Timeout de conexión (5.0s) o timeout de respuesta (5.0s)
3. **Monitor** → Incrementa `consecutive_failures += 1`
4. **Monitor** → Si `consecutive_failures >= 3`:
   - Reporta `ENGINE_FAILURE` a Central vía Kafka con `failure_type: 'timeout'`
   - Resetea `consecutive_failures = 0`
5. **Monitor** → Actualiza `shared_state.health_status` a `'TIMEOUT'`

**Estado**: ✅ **FUNCIONA CORRECTAMENTE**

---

## Verificación de Detalles

### ✅ Frecuencia de Health Checks

**Monitor** envía health check cada **1 segundo** ✅
- Ubicación: `await asyncio.sleep(1)` (línea 779)
- Cumple especificación del PDF

### ✅ Manejo de Errores

**Monitor** maneja correctamente:
- ✅ Timeout de conexión (5.0s)
- ✅ Timeout de lectura de respuesta (5.0s)
- ✅ Errores de conexión (ConnectionResetError, OSError, etc.)
- ✅ Datos parciales (IncompleteReadError)

### ✅ Conteo de Fallos

**Monitor** cuenta fallos consecutivos correctamente:
- ✅ Resetea contador cuando recibe "OK"
- ✅ Incrementa contador cuando recibe "KO" o timeout
- ✅ Reporta a Central tras 3 fallos consecutivos
- ✅ Resetea contador después de reportar

### ✅ Actualización de Estado

**Monitor** actualiza `shared_state.health_status` correctamente:
- ✅ `last_check`: Timestamp de última verificación
- ✅ `last_status`: "OK", "KO", o "TIMEOUT"
- ✅ `consecutive_failures`: Número de fallos consecutivos

### ✅ Reporte a Central

**Monitor** reporta correctamente a Central:
- ✅ Evento: `ENGINE_FAILURE`
- ✅ Acción: `report_engine_failure`
- ✅ Datos: `cp_id`, `failure_type`, `consecutive_failures`
- ✅ Topic: `monitor-events`

---

## Posibles Problemas Identificados

### ⚠️ PROBLEMA POTENCIAL 1: Muchos prints en logs

**Ubicación**: Monitor imprime cada conexión y respuesta

**Estado**: No es un problema funcional, pero puede generar mucho ruido en logs

**Recomendación**: Los prints ya están comentados/reducidos en la mayoría de casos ✅

### ✅ NO HAY PROBLEMAS FUNCIONALES

El sistema de health checks funciona correctamente:
- ✅ Monitor solicita estado cada 1 segundo
- ✅ Engine responde correctamente
- ✅ Monitor detecta fallos y timeouts
- ✅ Monitor reporta a Central tras 3 fallos consecutivos
- ✅ Manejo robusto de errores

---

## Conclusión

✅ **Monitor solicita estado del Engine correctamente cada 1 segundo**
✅ **Engine responde correctamente a health checks**
✅ **Monitor detecta fallos y reporta a Central correctamente**
✅ **Manejo robusto de errores y timeouts**

**Estado General**: ✅ **SISTEMA DE HEALTH CHECKS FUNCIONAL**

