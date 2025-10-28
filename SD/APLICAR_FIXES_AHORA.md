# 🚀 APLICAR FIXES - Instrucciones

## ✅ Cambios ya aplicados en el código:

1. **SD/EV_Central/EV_Central_WebSocket.py** (línea 884-930)
   - Corregido: Ahora usa `end_charging_sesion()` y `get_active_sesion_for_user()`
   - Agrega `user_id` si solo viene `username`

2. **SD/EV_Driver/EV_Driver_WebSocket.py** (línea 373-391)
   - Agrega `user_id` al evento `charging_stopped`

3. **SD/EV_Central/EV_Central_WebSocket.py** (línea 399-406, 433-439)
   - Publica eventos `CP_ERROR_SIMULATED` y `CP_ERROR_FIXED` en Kafka

4. **SD/EV_Driver/EV_Driver_WebSocket.py** (línea 161-196, 1162-1209)
   - Procesa eventos de error de CP desde Central

5. **SD/EV_Driver/dashboard.html** (línea 604-627)
   - Muestra errores de CP en la interfaz

---

## 📋 PASOS PARA APLICAR:

### 1. Iniciar Docker Desktop
   - Abre Docker Desktop y espera a que esté completamente iniciado
   - Verifica que el icono muestre "Docker Desktop is running"

### 2. En este PC (Central - PC2):

```powershell
cd C:\Users\luisb\Desktop\SD_Final\SD\SD
docker-compose -f docker-compose.pc2.yml down
docker-compose -f docker-compose.pc2.yml up -d --build
```

**Verificar logs:**
```powershell
docker logs ev-central --tail 30
```

**Debes ver:**
```
[CENTRAL] ✅ Kafka producer initialized
[KAFKA] 🔄 Attempt 1/15 to connect to Kafka at 172.20.10.8:9092
[KAFKA] ✅ Kafka consumer connected successfully
[HTTP] Server started on http://0.0.0.0:5001
```

### 3. En el otro PC (Driver - PC1):

```powershell
cd C:\Users\luisb\Desktop\SD_Final\SD\SD
docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc1.yml up -d --build
```

**Verificar logs:**
```powershell
docker logs ev-driver --tail 30
```

**Debes ver:**
```
[DRIVER] ✅ Kafka producer initialized
[KAFKA] 📡 Consumer started, listening to ['central-events']
[HTTP] Server started on http://0.0.0.0:8001
```

---

## 🧪 PRUEBAS PARA VERIFICAR QUE FUNCIONA:

### Prueba 1: Detener carga funciona correctamente

1. **Driver (PC1):**
   - Login como driver1
   - Solicitar carga → Se asigna CP_001
   - Click en "Detener Carga"

2. **Verificar en PC2 (Central):**
   ```powershell
   docker logs ev-central | Select-String "charging_stopped" -Context 2
   ```

   **Debes ver:**
   ```
   [CENTRAL] ⛔ Procesando charging_stopped: user=driver1, cp=CP_001, energy=X.X
   [CENTRAL] ✅ Sesión X finalizada: X.X kWh, coste=X.XX EUR
   ```

3. **Verificar en BD:**
   ```powershell
   python check_charging_state.py
   ```

   **Debes ver:**
   ```
   [OK] No hay sesiones activas sin cerrar
   ```

### Prueba 2: Errores de CP se notifican al Driver

1. **Central (PC2):**
   - Abrir dashboard admin: `http://localhost:5001` o `http://172.20.10.8:5001`
   - Login como admin / admin123
   - Seleccionar CP_001 (o el que esté usando el Driver)
   - Simular error "fault"

2. **Driver (PC1):**
   - Dashboard debe mostrar alert: "Error en tu punto de carga..."
   - Estado debe cambiar a "❌ ERROR EN CP"
   - Log debe mostrar: "⚠️ Error 'fault' simulado en CP_001"

3. **Verificar logs del Driver:**
   ```powershell
   docker logs ev-driver | Select-String "CP.*tiene error" -Context 1
   ```

   **Debes ver:**
   ```
   [DRIVER] ⚠️ CP CP_001 tiene error: fault
   [DRIVER] 📢 Notificando error a driver1
   ```

---

## 🔍 SI ALGO NO FUNCIONA:

### Problema: No se ven los logs esperados

**Solución:**
```powershell
# Ver logs completos
docker logs ev-central --tail 100
docker logs ev-driver --tail 100
```

### Problema: "No such container"

**Solución:**
```powershell
# Ver qué contenedores están corriendo
docker ps -a

# Si no están corriendo, iniciar:
docker-compose -f docker-compose.pc2.yml up -d --build
```

### Problema: Sesiones siguen sin cerrarse

**Solución:**
```powershell
# Ver si hay errores en Central
docker logs ev-central | Select-String "Error|ERROR|❌" -Context 2

# Verificar que el evento tiene user_id
docker logs ev-driver | Select-String "user_id=" -Context 1
```

---

## ✅ RESUMEN DE LO QUE SE CORRIGIÓ:

| Problema | Causa | Solución Aplicada |
|----------|-------|-------------------|
| Central no cierra sesiones | Nombres de funciones incorrectos | Usar `end_charging_sesion()` |
| Driver no recibe errores de CP | Central no publicaba en Kafka | Agregar `publish_event()` |
| Dashboard no muestra errores | Faltaba handler | Agregar case 'cp_error' |
| Central no encontraba user_id | Driver no lo enviaba | Agregar user_id al evento |

---

## 📝 COMANDOS RÁPIDOS:

```powershell
# PC2 (Central) - Todo en uno
docker-compose -f docker-compose.pc2.yml down && docker-compose -f docker-compose.pc2.yml up -d --build && docker logs ev-central --tail 30

# PC1 (Driver) - Todo en uno
docker-compose -f docker-compose.pc1.yml down && docker-compose -f docker-compose.pc1.yml up -d --build && docker logs ev-driver --tail 30

# Verificar BD
python check_charging_state.py
```

---

¡Listo! Los cambios están aplicados en el código. Solo falta rebuildar los contenedores cuando Docker esté corriendo. 🎉

