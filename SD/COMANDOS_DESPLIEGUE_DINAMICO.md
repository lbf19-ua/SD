# 📋 Comandos para Despliegue Dinámico de Instancias

## ⚠️ IMPORTANTE: Antes de ejecutar

1. **Obtén la IP de PC2** desde tu archivo `.env` o ejecutando en PC2:
   ```powershell
   ipconfig | findstr IPv4
   ```
   Ejemplo: `192.168.1.235`

2. **Asegúrate de estar en el directorio correcto** (PC3):
   ```powershell
   cd C:\Users\luisb\Desktop\SD_FINAL\SD\SD
   ```

---

## 🚀 Crear una nueva instancia de ENGINE (CP_005)

```powershell
docker run -d --name ev-cp-engine-005 `
  --network ev-network `
  -p 5104:5104 `
  -e CP_ID=CP_005 `
  -e LOCATION="Parking Central" `
  -e HEALTH_PORT=5104 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db `
  -v ${PWD}/network_config.py:/app/network_config.py `
  -v ${PWD}/database.py:/app/database.py `
  -v ${PWD}/event_utils.py:/app/event_utils.py `
  --restart unless-stopped `
  ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_005 --location "Parking Central" --health-port 5104 --kafka-broker 192.168.1.235:9092
```

**⚠️ Nota**: Cambia `192.168.1.235` por la IP real de PC2.

---

## 📊 Crear una nueva instancia de MONITOR (para CP_005)

```powershell
docker run -d --name ev-cp-monitor-005 `
  --network ev-network `
  -p 5504:5504 `
  -e CP_ID=CP_005 `
  -e ENGINE_HOST=ev-cp-engine-005 `
  -e ENGINE_PORT=5104 `
  -e MONITOR_PORT=5504 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db:ro `
  -v ${PWD}/network_config.py:/app/network_config.py:ro `
  -v ${PWD}/database.py:/app/database.py:ro `
  -v ${PWD}/event_utils.py:/app/event_utils.py:ro `
  -v ${PWD}/EV_CP_M/monitor_dashboard.html:/app/monitor_dashboard.html:ro `
  --restart unless-stopped `
  ev-cp-monitor-001 `
  python -u EV_CP_M_WebSocket.py --cp-id CP_005 --engine-host ev-cp-engine-005 --engine-port 5104 --monitor-port 5504 --kafka-broker 192.168.1.235:9092
```

**⚠️ Nota**: 
- Cambia `192.168.1.235` por la IP real de PC2.
- El Monitor necesita que el Engine ya esté corriendo (debería estar en la misma red Docker).

---

## 🛑 Simular CRASH de una instancia (detener abruptamente)

### Detener Engine:
```powershell
docker stop ev-cp-engine-005
# O más abrupto:
docker kill ev-cp-engine-005
```

### Detener Monitor:
```powershell
docker stop ev-cp-monitor-005
# O más abrupto:
docker kill ev-cp-monitor-005
```

---

## 🔄 Reiniciar una instancia después de un "crash"

```powershell
docker start ev-cp-engine-005
docker start ev-cp-monitor-005
```

---

## 📋 Ver logs de una instancia específica

```powershell
# Ver logs del Engine
docker logs -f ev-cp-engine-005

# Ver logs del Monitor
docker logs -f ev-cp-monitor-005
```

---

## ✅ Verificar que una instancia está funcionando

```powershell
# Ver estado de todos los contenedores
docker ps

# Ver solo las instancias de CP
docker ps --filter "name=ev-cp-"

# Verificar que el Engine responde en el puerto
Test-NetConnection localhost -Port 5104

# Verificar que el Monitor responde en el puerto
Test-NetConnection localhost -Port 5504
```

---

## 🌐 Acceder al Dashboard del Monitor

Abre en el navegador:
```
http://localhost:5504
```
O desde otro PC en la red:
```
http://[IP_PC3]:5504
```

---

## 🗑️ Eliminar una instancia completamente

```powershell
# Detener y eliminar el Monitor primero
docker stop ev-cp-monitor-005
docker rm ev-cp-monitor-005

# Detener y eliminar el Engine
docker stop ev-cp-engine-005
docker rm ev-cp-engine-005
```

---

## 📝 Notas importantes

1. **Orden de creación**: Siempre crea el Engine ANTES que el Monitor, porque el Monitor necesita conectarse al Engine.

2. **Puertos únicos**: Asegúrate de usar puertos únicos:
   - Engine: 5104, 5105, 5106... (el siguiente disponible)
   - Monitor: 5504, 5505, 5506... (el siguiente disponible)

3. **Network Docker**: Si la red `ev-network` no existe, créala primero:
   ```powershell
   docker network create ev-network
   ```

4. **Imagen Docker**: Los comandos asumen que ya has construido las imágenes con docker-compose. Si no:
   ```powershell
   docker-compose -f docker-compose.pc3.yml build
   ```

5. **Variables de entorno**: Si usas un archivo `.env`, puedes cargar las variables así:
   ```powershell
   # En PowerShell, leer desde .env
   Get-Content .env | ForEach-Object {
       $name, $value = $_ -split '=', 2
       [Environment]::SetEnvironmentVariable($name, $value, "Process")
   }
   # Luego usar en el comando: $env:KAFKA_BROKER
   ```

---

## 🔧 Ejemplo completo: Crear CP_006 con puertos 5105/5505

```powershell
# 1. Crear Engine CP_006
docker run -d --name ev-cp-engine-006 `
  --network ev-network `
  -p 5105:5105 `
  -e CP_ID=CP_006 `
  -e LOCATION="Parking Nuevo" `
  -e HEALTH_PORT=5105 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db `
  -v ${PWD}/network_config.py:/app/network_config.py `
  -v ${PWD}/database.py:/app/database.py `
  -v ${PWD}/event_utils.py:/app/event_utils.py `
  --restart unless-stopped `
  ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_006 --location "Parking Nuevo" --health-port 5105 --kafka-broker 192.168.1.235:9092

# 2. Esperar unos segundos a que el Engine inicie
Start-Sleep -Seconds 5

# 3. Crear Monitor CP_006
docker run -d --name ev-cp-monitor-006 `
  --network ev-network `
  -p 5505:5505 `
  -e CP_ID=CP_006 `
  -e ENGINE_HOST=ev-cp-engine-006 `
  -e ENGINE_PORT=5105 `
  -e MONITOR_PORT=5505 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e PYTHONUNBUFFERED=1 `
  -v ${PWD}/ev_charging.db:/app/ev_charging.db:ro `
  -v ${PWD}/network_config.py:/app/network_config.py:ro `
  -v ${PWD}/database.py:/app/database.py:ro `
  -v ${PWD}/event_utils.py:/app/event_utils.py:ro `
  -v ${PWD}/EV_CP_M/monitor_dashboard.html:/app/monitor_dashboard.html:ro `
  --restart unless-stopped `
  ev-cp-monitor-001 `
  python -u EV_CP_M_WebSocket.py --cp-id CP_006 --engine-host ev-cp-engine-006 --engine-port 5105 --monitor-port 5505 --kafka-broker 192.168.1.235:9092
```

---

## 🎯 Para la demostración de corrección

1. **Demostrar despliegue dinámico**:
   - Ejecuta los comandos para crear CP_005 y su Monitor
   - Muestra que aparecen en el dashboard del Central
   - Verifica que el Monitor puede supervisar el Engine

2. **Simular crash**:
   - Detén abruptamente el Engine con `docker kill ev-cp-engine-005`
   - Muestra que el Monitor detecta el fallo
   - Reinicia el Engine con `docker start ev-cp-engine-005`
   - Muestra que el Monitor detecta la recuperación

3. **Múltiples instancias**:
   - Crea varias instancias más (CP_006, CP_007)
   - Muestra que todas funcionan independientemente
   - Demuestra que cada una tiene su propio dashboard de Monitor

