# EV_CP_M (Electric Vehicle Charging Point Monitor)

## Descripción

El EV_CP_M es un módulo de gestión de observación que simula el monitoreo de hardware y software de un punto de carga (Charging Point). Su función principal es velar por la seguridad y correcto funcionamiento del sistema sin incidencias.

## Funcionalidades Implementadas

### 1. Autenticación con EV_Central
- Conexión inicial al EV_Central para autenticarse
- Validación de que el vehículo está operativo y preparado para prestar servicios
- Recibe parámetros de configuración:
  - IP y puerto del EV_CP_E (Engine)
  - IP y puerto del EV_Central
  - ID del Charging Point

### 2. Monitorización del Engine
- Conexión al Engine del CP al que pertenece
- Envío de mensajes de comprobación de estado **cada segundo**
- Detección de respuestas KO del Engine
- Reporte automático al EV_Central en caso de múltiples fallos

### 3. Gestión de Incidencias
- Detección de fallos consecutivos del Engine
- Reporte de averías al EV_Central cuando se detectan problemas persistentes
- Logging detallado de todos los eventos

### 4. Integración con Kafka
- Publicación de eventos en el topic `monitor-events`
- Registro de todas las acciones realizadas
- Facilita la monitorización y auditoría del sistema

## Uso

### Ejecución Básica
```bash
python EV_CP_M.py
```

### Ejecución con Parámetros Personalizados
```bash
python EV_CP_M.py --cp-id CP_001 --central-ip 192.168.1.235 --central-port 5000 --engine-ip localhost --engine-port 5001
```

### Prueba de Conexiones
```bash
python EV_CP_M.py --test
```

### Parámetros Disponibles
- `--cp-id`: ID del Charging Point (por defecto: CP_001)
- `--central-ip`: IP del servidor Central (por defecto: desde network_config.py)
- `--central-port`: Puerto del servidor Central (por defecto: 5000)
- `--engine-ip`: IP del Engine a monitorizar (por defecto: localhost)
- `--engine-port`: Puerto del Engine (por defecto: 5001)
- `--test`: Ejecutar solo pruebas de conexión

## Flujo de Operación

1. **Inicialización**
   - Inicializa el productor de Kafka
   - Configura parámetros de conexión

2. **Autenticación**
   - Se conecta al EV_Central
   - Envía mensaje de registro: `"EV_CP_M {cp_id} registration request"`
   - Espera confirmación de autenticación

3. **Conexión al Engine**
   - Se conecta al Engine del CP
   - Establece canal de comunicación para monitorización

4. **Monitorización Continua**
   - Envía mensajes de comprobación cada segundo
   - Analiza respuestas del Engine (OK/KO)
   - Cuenta fallos consecutivos

5. **Gestión de Fallos**
   - Si detecta 3 o más fallos consecutivos
   - Reporta al EV_Central: `"EV_CP_M {cp_id} ENGINE_FAILURE"`

## Eventos Kafka

El monitor publica los siguientes tipos de eventos:

### Registro con Central
```json
{
  "cp_id": "CP_001",
  "monitor_id": "EV_CP_M",
  "action": "register_to_central",
  "timestamp": 1640000000.0,
  "status": "connecting"
}
```

### Autenticación Exitosa
```json
{
  "cp_id": "CP_001",
  "monitor_id": "EV_CP_M", 
  "action": "authenticated_with_central",
  "timestamp": 1640000000.0,
  "status": "success"
}
```

### Verificación de Salud
```json
{
  "cp_id": "CP_001",
  "monitor_id": "EV_CP_M",
  "action": "health_check",
  "status": "OK",
  "engine_response": "OK",
  "consecutive_failures": 0,
  "timestamp": 1640000000.0
}
```

### Reporte de Fallo
```json
{
  "cp_id": "CP_001",
  "monitor_id": "EV_CP_M",
  "action": "report_engine_failure",
  "timestamp": 1640000000.0,
  "central_response": "Failure report received"
}
```

## Pruebas

### Script de Pruebas Automatizadas
```bash
python test_monitor.py
```

El script de pruebas incluye:
- **test_basic_connection**: Prueba conexiones básicas
- **test_engine_failure_detection**: Simula fallos del Engine
- **test_intermitent_failures**: Prueba fallos intermitentes

### Configuración para Pruebas Manuales

1. **Ejecutar EV_Central** (en otra terminal):
```bash
cd ../EV_Central
python EV_Central.py
```

2. **Ejecutar Engine simulado** (en otra terminal):
```bash
cd ../EV_CP_E  
python EV_CP_E.py
```

3. **Ejecutar Monitor**:
```bash
python EV_CP_M.py --cp-id CP_TEST_001
```

## Docker

### Construcción
```bash
docker build -t ev-cp-m .
```

### Ejecución
```bash
docker run -e CP_ID=CP_001 -e CENTRAL_IP=host.docker.internal -e ENGINE_IP=host.docker.internal ev-cp-m
```

## Arquitectura

```
EV_CP_M
├── Conexión TCP con EV_Central (autenticación)
├── Conexión TCP con EV_CP_E (monitorización)
├── Productor Kafka (eventos)
└── Bucle de monitorización (cada 1 segundo)
```

## Estados del Monitor

- **OK**: Engine respondiendo correctamente
- **KO**: Engine reportando problemas
- **CONNECTION_ERROR**: No es posible conectar al Engine
- **MONITORING**: En proceso de monitorización activa

## Logging

El monitor genera logs detallados de:
- Conexiones establecidas
- Respuestas del Engine
- Fallos detectados
- Reportes enviados al Central
- Eventos publicados en Kafka

## Requisitos

- Python 3.11+
- kafka-python
- Acceso de red a EV_Central y EV_CP_E
- Broker Kafka funcionando

## Configuración de Red

La configuración de IPs se gestiona a través de `network_config.py` en el directorio padre.