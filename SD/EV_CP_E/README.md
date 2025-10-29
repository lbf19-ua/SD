# EV_CP_E (Electric Vehicle Charging Point Engine)

## 📝 Descripción

El **EV_CP_E** (Engine) es el componente que simula el **hardware físico** de un punto de carga. Es responsable de ejecutar el proceso real de carga, responder a comandos de Central y reportar su estado.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────┐
│          EV_CP_E (Engine)               │
│  - Auto-registro al iniciar             │
│  - Kafka Consumer (comandos)            │
│  - Kafka Producer (eventos)             │
│  - TCP Server (health checks)           │
│  - Thread simulación de carga           │
└──────────┬──────────────────┬───────────┘
           │                  │
    ┌──────▼──────┐    ┌─────▼─────┐
    │   Central   │    │  Monitor  │
    │   (Kafka)   │    │   (TCP)   │
    └─────────────┘    └───────────┘
```

## ✨ Funcionalidades

### 1. **Auto-registro al iniciar**
- Al arrancar, envía evento `CP_REGISTRATION` a Kafka
- Central lo registra automáticamente en la base de datos
- Cambia estado a `available` cuando está listo

### 2. **Gestión de Estados**
Según especificación del PDF (página 4):
- 🟢 `available`: Disponible para cargar
- ⚡ `charging`: Cargando actualmente
- ⚫ `offline`: Desconectado
- 🔴 `fault`: Averiado (error de hardware)
- 🟠 `out_of_service`: Fuera de servicio (mantenimiento)

### 3. **Simulación de Carga**
- Simula consumo de energía realista (80-95% de potencia máxima)
- Actualiza energía cada segundo
- Publica progreso cada 5 segundos
- Calcula coste en tiempo real

### 4. **Health Checks (para Monitor)**
- Servidor TCP en puerto configurable (default: 5100)
- Responde "OK" o "KO" cada segundo
- El Monitor usa esto para detectar fallos

### 5. **Responder a Comandos**
Escucha eventos de Central vía Kafka:
- `charging_started`: Iniciar carga
- `charging_stopped`: Detener carga
- `CP_ERROR_SIMULATED`: Simular error
- `CP_ERROR_FIXED`: Reparar error

## 🚀 Uso

### **Ejecución Básica**
```bash
python EV_CP_E.py
```

### **Con Parámetros Personalizados**
```bash
python EV_CP_E.py \
    --cp-id CP_Norte_01 \
    --location "Parking Norte - Plaza 5" \
    --max-power 50.0 \
    --tariff 0.35 \
    --health-port 5100 \
    --kafka-broker 172.20.10.8:9092
```

### **Múltiples CPs simultáneos**
```bash
# Terminal 1
python EV_CP_E.py --cp-id CP_001 --health-port 5101

# Terminal 2
python EV_CP_E.py --cp-id CP_002 --health-port 5102 --location "Parking Sur"

# Terminal 3
python EV_CP_E.py --cp-id CP_003 --health-port 5103 --max-power 50
```

## 🔧 Parámetros Disponibles

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--cp-id` | ID único del Charging Point | `CP_001` |
| `--location` | Ubicación física | `"Unknown Location"` |
| `--max-power` | Potencia máxima (kW) | `22.0` |
| `--tariff` | Tarifa por kWh (€) | `0.30` |
| `--health-port` | Puerto TCP para health checks | `5100` |
| `--kafka-broker` | Dirección del broker Kafka | Desde config |

## 📡 Eventos Kafka

### **Publicados (Topic: `cp-events`)**

#### Auto-registro
```json
{
  "message_id": "uuid-here",
  "event_type": "CP_REGISTRATION",
  "cp_id": "CP_001",
  "action": "connect",
  "data": {
    "location": "Parking Norte",
    "max_power_kw": 22.0,
    "tariff_per_kwh": 0.30
  },
  "timestamp": 1640000000.0
}
```

#### Cambio de Estado
```json
{
  "message_id": "uuid-here",
  "event_type": "cp_status_change",
  "cp_id": "CP_001",
  "action": "cp_status_change",
  "status": "charging",
  "previous_status": "available",
  "reason": "Charging started for user driver1",
  "timestamp": 1640000000.0
}
```

#### Progreso de Carga (cada 5s)
```json
{
  "message_id": "uuid-here",
  "event_type": "charging_progress",
  "cp_id": "CP_001",
  "action": "charging_progress",
  "username": "driver1",
  "energy_kwh": 5.234,
  "cost": 1.57,
  "power_kw": 20.5,
  "timestamp": 1640000000.0
}
```

### **Consumidos (Topic: `central-events`)**

- `AUTHORIZATION_RESPONSE`: Respuesta de autorización
- `charging_started`: Orden de iniciar carga
- `charging_stopped`: Orden de detener carga
- `CP_ERROR_SIMULATED`: Simular error
- `CP_ERROR_FIXED`: Reparar error

## 🏥 Health Check Protocol

El Engine ejecuta un servidor TCP simple:

```python
# Monitor pregunta:
"STATUS?"

# Engine responde:
"OK"  # Si todo funciona bien
"KO"  # Si hay un error (status == 'fault')
```

## 🐳 Docker

### **Build**
```bash
docker build -t ev-cp-engine .
```

### **Run**
```bash
docker run \
  -e CP_ID=CP_Docker_01 \
  -e LOCATION="Parking Docker" \
  -e KAFKA_BROKER=host.docker.internal:9092 \
  -p 5100:5100 \
  ev-cp-engine
```

### **Docker Compose**
```yaml
services:
  cp-engine-1:
    build: ./EV_CP_E
    environment:
      CP_ID: CP_001
      LOCATION: "Parking Norte"
      KAFKA_BROKER: kafka:9092
    ports:
      - "5101:5100"
    depends_on:
      - kafka
  
  cp-engine-2:
    build: ./EV_CP_E
    environment:
      CP_ID: CP_002
      LOCATION: "Parking Sur"
      KAFKA_BROKER: kafka:9092
    ports:
      - "5102:5100"
    depends_on:
      - kafka
```

## 📊 Flujo de Operación

### **1. Startup**
```
[Engine] Conectando a Kafka...
[Engine] ✅ Kafka connected
[Engine] 📝 Auto-registering with Central...
[Engine] 🔄 Status change: offline → available
[Engine] 🏥 Health check server started on port 5100
[Engine] ✅ All systems operational
[Engine] 🔋 Ready to charge vehicles
[Engine] 👂 Listening for commands from Central...
```

### **2. Inicio de Carga**
```
[Engine] 📨 Received: charging_started
[Engine] 🔄 Status change: available → charging
[Engine] ⚡ Starting charging simulation for user: driver1
[Engine] 📤 Published event: cp_status_change
```

### **3. Durante la Carga**
```
[Engine] 📤 Published event: charging_progress
   Energy: 2.45 kWh | Cost: €0.74
[Engine] 📤 Published event: charging_progress
   Energy: 4.89 kWh | Cost: €1.47
```

### **4. Detener Carga**
```
[Engine] 📨 Received: charging_stopped
[Engine] ⛔ Charging stopped for driver1
   Energy: 15.34 kWh | Cost: €4.60
[Engine] 🔄 Status change: charging → available
[Engine] ✅ Charging session completed
```

### **5. Simulación de Error**
```
[Engine] 📨 Received: CP_ERROR_SIMULATED
[Engine] 🚨 Simulating error: fault
[Engine] 🔄 Status change: available → fault
[Engine] Health status: OK → KO
```

## 🔄 Integración con Otros Componentes

### **Con EV_Central**
- Recibe comandos vía Kafka (`central-events`)
- Publica eventos vía Kafka (`cp-events`)
- Central lo registra automáticamente al iniciar

### **Con EV_CP_M (Monitor)**
- Responde health checks cada segundo vía TCP
- Monitor detecta fallos si responde "KO" 3+ veces
- Monitor reporta a Central si hay problemas

### **Con EV_Driver**
- No hay comunicación directa
- Toda la coordinación pasa por Central

## 🧪 Testing

### **Test Manual Básico**

1. **Iniciar Kafka**
```bash
docker-compose up -d
```

2. **Iniciar Central**
```bash
cd SD/EV_Central
python EV_Central_WebSocket.py
```

3. **Iniciar Engine**
```bash
cd SD/EV_CP_E
python EV_CP_E.py --cp-id CP_TEST_001
```

4. **Verificar auto-registro**
- Abrir: http://localhost:8002 (Admin Dashboard)
- Ver que CP_TEST_001 aparece con estado "available"

5. **Iniciar Driver**
```bash
cd SD/EV_Driver
python EV_Driver_WebSocket.py
```

6. **Solicitar carga**
- Abrir: http://localhost:8001 (Driver Dashboard)
- Login: driver1 / pass123
- Click "Iniciar Carga"
- Ver que el Engine cambia a "charging"

### **Test con Monitor**

```bash
# Terminal 1: Engine
python EV_CP_E.py --cp-id CP_001 --health-port 5100

# Terminal 2: Monitor
cd ../EV_CP_M
python EV_CP_M_WebSocket.py --cp-id CP_001 --engine-port 5100
```

## 📋 Requisitos

- Python 3.11+
- kafka-python
- Broker Kafka funcionando
- EV_Central corriendo

## ⚠️ Notas Importantes

1. **Puerto Health Check único**: Si ejecutas múltiples CPs, cada uno necesita su propio puerto (`--health-port`)

2. **CP_ID único**: Cada Engine debe tener un `cp_id` diferente

3. **Kafka debe estar corriendo**: El Engine no arranca sin Kafka

4. **Auto-registro**: No necesitas crear el CP manualmente en BD, el Engine se registra solo al iniciar

## 🐛 Troubleshooting

### Engine no se conecta a Kafka
```bash
# Verificar que Kafka está corriendo
docker ps | grep kafka

# Verificar conectividad
telnet 172.20.10.8 9092
```

### Health checks no funcionan
```bash
# Probar conexión TCP manualmente
telnet localhost 5100
STATUS?
# Debe responder: OK
```

### CP no aparece en Central
- Verificar logs de Central
- Verificar que el topic `cp-events` existe
- Verificar que el evento CP_REGISTRATION se publicó

## 📚 Referencias

- **network_config.py**: Configuración de IPs y puertos
- **event_utils.py**: Utilidades para eventos
- **Kafka Topics**: Definidos en network_config.KAFKA_TOPICS

