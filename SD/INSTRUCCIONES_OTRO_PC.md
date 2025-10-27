# 🔧 Instrucciones para el Otro PC - Corregir Error de WebSocket

## Problema Identificado

Driver está recibiendo la autorización de Central y diciendo "✅ Central autorizó carga en CP_001", pero **NO aparece el mensaje de "Sesión X creada"**, lo que significa que `create_charging_session()` no se está ejecutando o falla silenciosamente.

## Cambios Realizados

Se corrigió el error de WebSocket que causaba:
```
RuntimeWarning: coroutine 'WebSocketResponse.send_str' was never awaited
```

## Pasos en el Otro PC

### 1. Detener Driver
```powershell
docker-compose -f docker-compose.pc1.yml down
```

### 2. Copiar el archivo actualizado

**Opción A: Desde USB**
- Copia `SD/EV_Driver/EV_Driver_WebSocket.py` del USB al otro PC

**Opción B: Reconstruir**
- Asegúrate de que tienes el archivo actualizado en el otro PC
- O bien, haz un rebuild completo:
```powershell
docker-compose -f docker-compose.pc1.yml up -d --build
```

### 3. Verificar logs

```powershell
docker logs ev-driver -f
```

**Debes ver ahora:**
```
[DRIVER] ✅ Central autorizó carga en CP_001
[DRIVER] ✅ Sesión X creada para driver1 en CP_001
```

**Si no aparece "Sesión X creada", ejecuta:**
```powershell
docker logs ev-driver | Select-String -Pattern "Error|Exception|Traceback" -Context 3
```

## Test Completo

1. Abre http://localhost:8001 en el otro PC
2. Login como `driver1` / `pass123`
3. Selecciona CP_001
4. Click en "Start Charging"
5. **En los logs debe aparecer:**
   ```
   [DRIVER] ✅ Central autorizó carga en CP_001
   [DRIVER] ✅ Sesión X creada para driver1 en CP_001
   ```
6. **En el dashboard de Central** (este PC):
   - CP_001 debe pasar de `reserved` a `charging`
   - Debe aparecer en "Sesiones Activas"

