# 🚀 Ejecutar Driver DIRECTAMENTE (sin Docker) - PC del Driver

## 📍 Configuración Requerida

### PC del Central (172.20.10.8)
- ✅ Kafka corriendo en puerto 9092
- ✅ Central corriendo en puerto 8002
- ✅ Firewall abierto puerto 9092

### PC del Driver
- 📂 Tener todos los archivos del proyecto
- 🐍 Tener Python 3.11+ instalado
- 📦 Tener instaladas las dependencias

## ⚙️ Instalación de Dependencias

En el PC del Driver, abre PowerShell y ejecuta:

```powershell
cd SD
pip install kafka-python websockets aiohttp
```

## 🔧 Configurar network_config.py

Asegúrate de que `network_config.py` tenga:

```python
# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "172.20.10.8"  # ← IP DEL CENTRAL

# Puerto de Kafka
KAFKA_PORT = 9092
KAFKA_BROKER = f"{PC2_IP}:{KAFKA_PORT}"
```

## 🚀 Ejecutar el Driver

```powershell
cd SD/EV_Driver
python EV_Driver_WebSocket.py
```

Deberías ver:
```
================================================================================
                    🚗 EV DRIVER - WebSocket Server
================================================================================
  🌐 Local Access:     http://localhost:8001
  🌍 Network Access:   http://TU_IP_LOCAL:8001
  🔌 WebSocket:        ws://TU_IP_LOCAL:8001/ws
  💾 Database:         ev_charging.db
  📡 Kafka Broker:     172.20.10.8:9092
  📤 Publishing:       driver-events
  🏢 Central Server:   172.20.10.8:5000
================================================================================
```

## ✅ Verificar que Funciona

1. Abre http://localhost:8001 en el navegador
2. Login: `driver1` / `pass123`
3. Click en "Solicitar Carga"
4. Deberías ver: "Carga iniciada en CP_XXX"

## 🐛 Troubleshooting

### Error: "Kafka not available"
```powershell
# Verificar conectividad
Test-NetConnection -ComputerName 172.20.10.8 -Port 9092
```

### Error: "No module named 'kafka'"
```powershell
pip install kafka-python
```

### Error: "No module named 'websockets'"
```powershell
pip install websockets aiohttp
```

## 📊 Verificar Flujo Completo

En el **PC del Central**, monitorea los logs:
```powershell
docker logs ev-central -f
```

Cuando el Driver solicite carga, deberías ver:
```
[CENTRAL] 🔐 Solicitud de autorización: usuario=driver1, buscando CP disponible...
[CENTRAL] 🎯 CP CP_001 asignado y reservado automáticamente para driver1
[CENTRAL] 📨 Received event: charging_started from topic: driver-events
[CENTRAL] ⚡ Suministro iniciado - Sesión X en CP CP_001 para usuario driver1
```

✅ Si ves estos logs, **TODO FUNCIONA**.

## 📝 Notas

- ✅ Ejecutar con Python evita problemas de red de Docker
- ✅ Conexión directa a Kafka sin problemas de contenedores
- ✅ Más fácil de debuggear
- ✅ No necesitas `network_mode: host` ni configuración especial


