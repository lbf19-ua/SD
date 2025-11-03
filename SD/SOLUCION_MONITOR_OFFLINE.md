# 🔧 Solución: Monitor Reporta Engine Offline

## Problema
El Monitor reporta constantemente que el Engine está offline, aunque el Engine aparece como "disponible" en el sistema.

## Causas Comunes

### 1. **Hostname Incorrecto**
El Monitor debe usar el **nombre del contenedor Docker** del Engine, NO `localhost`.

**❌ Incorrecto:**
```powershell
--engine-host localhost
```

**✅ Correcto:**
```powershell
--engine-host ev-cp-engine-005
```

### 2. **Red Docker Diferente**
Ambos contenedores (Engine y Monitor) deben estar en la **misma red Docker**.

**Verificar:**
```powershell
docker inspect ev-cp-engine-005 | Select-String "NetworkMode"
docker inspect ev-cp-monitor-005 | Select-String "NetworkMode"
```

Deben mostrar `ev-network` o la misma red.

### 3. **Engine No Tiene Servidor TCP Iniciado**
El Engine debe iniciar su servidor TCP de health checks.

**Verificar:**
```powershell
docker logs ev-cp-engine-005 | Select-String "Health check server started"
```

Debe mostrar: `🏥 Health check server started on port 5104`

---

## 🔍 Diagnóstico

### Paso 1: Verificar que el Engine está escuchando
```powershell
# Ver logs del Engine
docker logs ev-cp-engine-005 --tail 50 | Select-String "Health check|TCP|5104"

# Verificar que el puerto está abierto dentro del contenedor
docker exec ev-cp-engine-005 python -c "import socket; s=socket.socket(); s.bind(('0.0.0.0', 5104)); print('Puerto disponible')"
```

### Paso 2: Verificar hostname que usa el Monitor
```powershell
# Ver logs del Monitor
docker logs ev-cp-monitor-005 --tail 50 | Select-String "Engine Host|Attempting to connect"

# Debe mostrar algo como:
# Engine Host: ev-cp-engine-005
# Attempting to connect to ev-cp-engine-005:5104
```

### Paso 3: Probar conectividad desde el Monitor
```powershell
# Ejecutar dentro del contenedor del Monitor
docker exec ev-cp-monitor-005 python -c "import socket; s=socket.socket(); s.connect(('ev-cp-engine-005', 5104)); print('✅ Conectividad OK')"
```

---

## ✅ Solución

### Opción 1: Recrear el Monitor con hostname correcto

```powershell
# 1. Detener y eliminar el Monitor actual
docker stop ev-cp-monitor-005
docker rm ev-cp-monitor-005

# 2. Verificar que el Engine está corriendo
docker ps --filter "name=ev-cp-engine-005"

# 3. Crear Monitor con hostname correcto
cd C:\Users\luisb\Desktop\SD_FINAL\SD\SD

docker run -d --name ev-cp-monitor-005 `
  --network ev-network `
  -p 5504:5504 `
  sd-ev-cp-monitor-001 `
  python -u EV_CP_M_WebSocket.py `
    --cp-id CP_005 `
    --engine-host ev-cp-engine-005 `
    --engine-port 5104 `
    --monitor-port 5504 `
    --kafka-broker 192.168.1.235:9092
```

### Opción 2: Verificar que el Engine tiene el servidor TCP corriendo

```powershell
# Ver logs completos del Engine
docker logs ev-cp-engine-005 | Select-String "Health check|TCP|port|listening"

# Si no aparece "Health check server started", el Engine tiene un problema
# Reiniciar el Engine:
docker restart ev-cp-engine-005

# Verificar nuevamente
docker logs ev-cp-engine-005 --tail 30 | Select-String "Health check"
```

---

## 📋 Checklist de Verificación

- [ ] El Engine está corriendo: `docker ps | Select-String "ev-cp-engine-005"`
- [ ] El Engine muestra "Health check server started": `docker logs ev-cp-engine-005 | Select-String "Health check"`
- [ ] El Monitor usa el nombre correcto del contenedor: `docker logs ev-cp-monitor-005 | Select-String "Engine Host"`
- [ ] Ambos están en la misma red: `docker network inspect ev-network`
- [ ] Conectividad funciona: `docker exec ev-cp-monitor-005 python -c "import socket; s=socket.socket(); s.connect(('ev-cp-engine-005', 5104)); print('OK')"`

---

## 🎯 Comando Rápido para Verificar Todo

```powershell
Write-Host "=== DIAGNÓSTICO COMPLETO ===" -ForegroundColor Green

Write-Host "`n1. Estado de contenedores:" -ForegroundColor Yellow
docker ps --filter "name=ev-cp-engine-005|ev-cp-monitor-005" --format "table {{.Names}}\t{{.Status}}"

Write-Host "`n2. Engine - Health Check Server:" -ForegroundColor Yellow
docker logs ev-cp-engine-005 2>&1 | Select-String "Health check server" | Select-Object -Last 1

Write-Host "`n3. Monitor - Hostname configurado:" -ForegroundColor Yellow
docker logs ev-cp-monitor-005 2>&1 | Select-String "Engine Host" | Select-Object -Last 1

Write-Host "`n4. Monitor - Intentos de conexión:" -ForegroundColor Yellow
docker logs ev-cp-monitor-005 2>&1 | Select-String "Attempting to connect|offline" | Select-Object -Last 5

Write-Host "`n5. Test de conectividad:" -ForegroundColor Yellow
docker exec ev-cp-monitor-005 python -c "import socket; s=socket.socket(); s.settimeout(2); result = s.connect_ex(('ev-cp-engine-005', 5104)); print('✅ Conectividad OK' if result == 0 else '❌ No puede conectar')" 2>&1
```

