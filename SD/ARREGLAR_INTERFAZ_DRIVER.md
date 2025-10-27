# 🔧 Solución: Interfaz Driver no se inicializa

## ⚠️ Problema Identificado

Los Dockerfiles de `EV_Driver` y `EV_CP_M` tenían la ruta incorrecta en el comando CMD.

## ✅ Solución Aplicada

Se corrigieron los siguientes archivos:

### 1. `SD/EV_Driver/Dockerfile`
**Antes:**
```dockerfile
CMD ["python", "EV_Driver_WebSocket.py"]
```

**Después:**
```dockerfile
WORKDIR /app/EV_Driver
CMD ["python", "EV_Driver_WebSocket.py"]
```

### 2. `SD/EV_CP_M/Dockerfile`
**Antes:**
```dockerfile
CMD ["python", "EV_CP_M_WebSocket.py"]
```

**Después:**
```dockerfile
WORKDIR /app/EV_CP_M
CMD ["python", "EV_CP_M_WebSocket.py"]
```

### 3. `SD/docker-compose.pc1.yml` y `SD/docker-compose.pc3.yml`
Se añadió `:ro` (read-only) a los volúmenes para evitar problemas de escritura.

---

## 🚀 Pasos para aplicar la solución en el OTRO PC

### 1️⃣ Actualizar los archivos en el otro PC

Copia estos archivos desde ESTE PC al OTRO PC:

```powershell
# En el OTRO PC, desde el directorio SD/
# Copia estos archivos:
# - SD/EV_Driver/Dockerfile
# - SD/EV_CP_M/Dockerfile
# - SD/docker-compose.pc1.yml
# - SD/docker-compose.pc3.yml
```

### 2️⃣ Reconstruir los contenedores

En el OTRO PC, ejecuta:

```powershell
cd C:\Users\[TU_USUARIO]\Desktop\SD\SD

# Reconstruir Driver
docker-compose -f docker-compose.pc1.yml down
docker-compose -f docker-compose.pc1.yml up -d --build

# Esperar 10 segundos
Start-Sleep -Seconds 10

# Reconstruir Monitor
docker-compose -f docker-compose.pc3.yml down
docker-compose -f docker-compose.pc3.yml up -d --build
```

### 3️⃣ Verificar logs

```powershell
# Ver logs de Driver
docker logs ev-driver --tail=30

# Deberías ver algo como:
# [DRIVER] ✅ Kafka producer initialized
# [HTTP] 🌐 Server started on http://0.0.0.0:8001

# Ver logs de Monitor
docker logs ev-monitor --tail=30

# Deberías ver algo como:
# [MONITOR] ✅ Kafka producer initialized
# [HTTP] 🌐 Server started on http://0.0.0.0:8003
```

### 4️⃣ Acceder a las interfaces

```powershell
# Abrir Dashboard Driver
Start-Process "http://localhost:8001"

# Abrir Dashboard Monitor
Start-Process "http://localhost:8003"
```

---

## ✅ Verificación Final

### En el OTRO PC:

1. **Ver contenedores corriendo:**
   ```powershell
   docker ps
   ```
   Deberías ver `ev-driver` y `ev-monitor` con estado `Up`.

2. **Verificar que las interfaces funcionan:**
   - Driver: http://localhost:8001
   - Monitor: http://localhost:8003

3. **Probar conexión con Central:**
   - En el Driver, intenta solicitar un servicio
   - Verifica en Kafka UI (http://192.168.1.235:8080) que los mensajes llegan

---

## 🐛 Si sigue sin funcionar

### Verificar los logs con más detalle:
```powershell
# Logs completos
docker logs ev-driver --tail=100
docker logs ev-monitor --tail=100

# Buscar errores específicos
docker logs ev-driver 2>&1 | Select-String "Error"
docker logs ev-monitor 2>&1 | Select-String "Error"
```

### Errores comunes:

#### Error: "Module not found"
**Solución:** Verifica que todos los archivos necesarios están copiados en el Dockerfile.

#### Error: "NoBrokersAvailable"
**Solución:** Verifica el firewall en ESTE PC (PC Central) con `.\configurar_firewall.ps1`

#### Error: "Permission denied"
**Solución:** Verifica que la base de datos existe y tiene permisos correctos:
```powershell
ls -la SD/ev_charging.db
```

---

¡Interfaz listo para funcionar! 🎉

