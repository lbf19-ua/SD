# 📋 Comando para Crear Nueva Instancia de Driver

## 🚗 Crear Driver en puerto 8002 (PC1)

```powershell
# Asegúrate de estar en el directorio correcto (PC1)
cd C:\Users\luisb\Desktop\SD_FINAL\SD\SD

# Crear nueva instancia de Driver en puerto 8002
docker run -d --name ev-driver-002 `
  --network ev-network `
  -p 8002:8002 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e CENTRAL_IP=192.168.1.235 `
  -e DRIVER_PORT=8002 `
  -e PYTHONUNBUFFERED=1 `
  -v "${PWD}\ev_charging.db:/app/ev_charging.db" `
  -v "${PWD}\network_config.py:/app/network_config.py" `
  -v "${PWD}\database.py:/app/database.py" `
  -v "${PWD}\event_utils.py:/app/event_utils.py" `
  -v "${PWD}\EV_Driver\dashboard.html:/app/dashboard.html" `
  -v "${PWD}\EV_Driver\servicios.txt:/app/servicios.txt" `
  --restart unless-stopped `
  sd-ev-driver `
  python -u EV_Driver_WebSocket.py --port 8002 --kafka-broker 192.168.1.235:9092 --central-ip 192.168.1.235
```

**⚠️ Nota**: Cambia `192.168.1.235` por la IP real de PC2 (donde está Kafka y Central).

---

## 🎯 Variantes del Comando

### **Driver con puerto 8003:**
```powershell
docker run -d --name ev-driver-003 `
  --network ev-network `
  -p 8003:8003 `
  -e KAFKA_BROKER=192.168.1.235:9092 `
  -e CENTRAL_IP=192.168.1.235 `
  -e DRIVER_PORT=8003 `
  -e PYTHONUNBUFFERED=1 `
  -v "${PWD}\ev_charging.db:/app/ev_charging.db" `
  -v "${PWD}\network_config.py:/app/network_config.py" `
  -v "${PWD}\database.py:/app/database.py" `
  -v "${PWD}\event_utils.py:/app/event_utils.py" `
  -v "${PWD}\EV_Driver\dashboard.html:/app/dashboard.html" `
  -v "${PWD}\EV_Driver\servicios.txt:/app/servicios.txt" `
  --restart unless-stopped `
  sd-ev-driver `
  python -u EV_Driver_WebSocket.py --port 8003 --kafka-broker 192.168.1.235:9092 --central-ip 192.168.1.235
```

---

## ✅ Verificar que Funciona

```powershell
# Ver estado del contenedor
docker ps --filter "name=ev-driver-002"

# Ver logs
docker logs ev-driver-002 --tail 30

# Verificar que el puerto está escuchando
Test-NetConnection localhost -Port 8002
```

---

## 🌐 Acceder al Dashboard

Abre en el navegador:
```
http://localhost:8002
```
O desde otro PC en la red:
```
http://[IP_PC1]:8002
```

---

## 🛑 Detener o Eliminar

```powershell
# Detener
docker stop ev-driver-002

# Eliminar
docker stop ev-driver-002
docker rm ev-driver-002
```

---

## 📝 Notas

1. **Puerto único**: Cada Driver debe tener un puerto diferente (8001, 8002, 8003...)

2. **Misma base de datos**: Todos los Drivers comparten la misma base de datos (`ev_charging.db`)

3. **Misma configuración de red**: Todos usan la misma red Docker `ev-network`

4. **Parámetros personalizables**:
   - `--port`: Puerto del dashboard
   - `--kafka-broker`: Dirección del broker Kafka
   - `--central-ip`: IP del servidor Central

5. **Si la red `ev-network` no existe**, créala primero:
   ```powershell
   docker network create ev-network
   ```

