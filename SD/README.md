# EV Charging System - Sistemas Distribuidos 2025

Sistema distribuido para gestión de puntos de carga de vehículos eléctricos implementado con Kafka, Sockets TCP, WebSockets y SQLite.

## 📚 DOCUMENTACIÓN COMPLETA

### 🚀 Guías de Instalación y Despliegue
- **[QUICK_DEPLOY_10_STEPS.md](QUICK_DEPLOY_10_STEPS.md)** ⭐ - Guía rápida de 10 pasos para desplegar el sistema
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** 📖 - Guía completa de despliegue en 3 PCs con todos los detalles
- **[INSTALLATION_CHECKLIST.md](INSTALLATION_CHECKLIST.md)** ✅ - Checklist detallado para cada PC
- **[DOWNLOADS_GUIDE.md](DOWNLOADS_GUIDE.md)** 📥 - Enlaces de descarga de todo el software necesario

### 🌐 Interfaces Web
- **[WEB_INTERFACES_README.md](WEB_INTERFACES_README.md)** 🖥️ - Documentación completa de las interfaces WebSocket
- **[QUICK_START.md](QUICK_START.md)** ⚡ - Inicio rápido de las interfaces web
- **[README_INTERFACES.md](README_INTERFACES.md)** 📄 - Resumen ejecutivo de las interfaces

### 📊 Estado del Proyecto
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Estado de implementación
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Resumen de la implementación

---

## 🏗️ Arquitectura del Sistema

El sistema está compuesto por los siguientes componentes distribuidos:

### Core System (EV_Central)
- **EV_Central.py**: Módulo central que gestiona todo el sistema (CLI)
- **EV_Central_WebSocket.py**: Servidor WebSocket para interfaz web administrativa
- **admin_dashboard.html**: Dashboard web para administración
- Servidor TCP para comunicación con clientes (Driver, Monitor, Engine)
- Productor/Consumidor de eventos Kafka
- Base de datos SQLite para persistencia
- Autenticación de usuarios y gestión de sesiones
- Asignación automática de puntos de carga

### Charging Points (EV_CP_E y EV_CP_M)
#### Engine (EV_CP_E)
- **EV_CP_E.py**: Simula el funcionamiento de un punto de carga
- Servidor TCP para comunicación con Monitor
- Publica eventos de estado en Kafka
- Simula proceso de carga con consumo de energía

#### Monitor (EV_CP_M)
- **EV_CP_M.py**: Monitoriza la salud del punto de carga (CLI)
- **EV_CP_M_WebSocket.py**: Servidor WebSocket para interfaz web de monitorización
- **monitor_dashboard.html**: Dashboard web para monitorización de CPs
- Cliente TCP para consultar estado del Engine
- Publica eventos de monitorización en Kafka
- Detecta fallos y genera alertas

### Driver App (EV_Driver)
- **EV_Driver.py**: Aplicación para conductores (CLI)
- **EV_Driver_WebSocket.py**: Servidor WebSocket para interfaz web de conductores
- **dashboard.html**: Dashboard web para solicitar y monitorizar carga
- Cliente TCP para comunicación con Central
- Autenticación de usuarios
- Solicitud y finalización de sesiones de carga
- Consulta de balance y historial

### Base de Datos (SQLite)
- **database.py**: Módulo de persistencia
- Gestión de usuarios con autenticación
- Registro de puntos de carga
- Sesiones de carga con cálculo de costos
- Log de eventos para auditoría
- Correlation IDs para trazabilidad

## 🌐 Interfaces de Usuario

### 🚗 Driver Dashboard (Puerto 8001)
- Login de usuarios
- Solicitud de carga
- Monitorización en tiempo real (energía, coste, progreso)
- Control de sesión (parar carga)
- Visualización de saldo

### 👨‍💼 Admin Dashboard (Puerto 8002)
- Estadísticas globales del sistema
- Sesiones activas en tiempo real
- Estado de todos los puntos de carga
- Lista de usuarios
- Stream de eventos en vivo

### 📊 Monitor Dashboard (Puerto 8003)
- Grid de puntos de carga con estado
- Alertas del sistema
- Gráficos de uso y eficiencia
- Métricas detalladas por CP (temperatura, potencia, etc.)

## 📡 Comunicación

### Sockets TCP
- **EV_Central ↔ EV_Driver**: Puerto 5001 (autenticación y solicitudes)
- **EV_Central**: Puerto 5002 (servidor central)
- **EV_CP_M**: Puerto 5003 (monitor)
- **EV_CP_E**: Puerto 5004 (engine)

### WebSockets (Interfaces Web)
- **EV_Driver WebSocket**: Puerto 8001 (dashboard conductores)
- **EV_Central WebSocket**: Puerto 8002 (dashboard admin)
- **EV_CP_M WebSocket**: Puerto 8003 (dashboard monitor)

### Kafka (Streaming & QM)
- **Topics**:
  - `driver-events`: Eventos de drivers
  - `cp-events`: Eventos de puntos de carga (Engine + Monitor)
  - `central-events`: Eventos del sistema central
- **Broker**: localhost:9092 (configurable por IP en red local)

## 🚀 Instalación y Ejecución

### Prerrequisitos
- Python 3.11+
- Kafka (broker Apache)
- Dependencias: `kafka-python`, `sqlite3` (incluido en Python)

### 1. Inicializar Base de Datos

```bash
cd c:\Users\luisb\Desktop\SD\SD
python init_db.py
```

Esto creará:
- Base de datos `ev_charging.db`
- Usuarios de prueba (driver1, driver2, admin)
- Puntos de carga iniciales (CP_001, CP_002, CP_003)

### 2. Configurar Red Local

Edita `network_config.py` para establecer las IPs reales de cada PC:

```python
CENTRAL_CONFIG = {'ip': '192.168.1.100', 'port': 5000}
CP_ENGINE_CONFIG = {'ip': '192.168.1.101', 'port': 9000}
# ... etc
```

### 3. Iniciar Kafka

En el PC designado para Kafka:
```bash
# Iniciar Kafka (modo KRaft)
kafka-server-start.sh config/kraft/server.properties
```

### 4. Ejecutar Componentes Distribuidos

**PC 1 - Sistema Central:**
```bash
python EV_Central/EV_Central.py
```

**PC 2 - Punto de Carga 1:**
```bash
# Terminal 1: Engine
python EV_CP_E/EV_CP_E.py

# Terminal 2: Monitor
python EV_CP_M/EV_CP_M.py
```

**PC 3 - Driver:**
```bash
python EV_Driver/EV_Driver.py
```

## 🧪 Pruebas del Sistema

### Escenario 1: Autenticación y Solicitud de Carga

1. Ejecutar Driver App
2. Autenticarse con `driver1` / `pass123`
3. Solicitar carga
4. Observar asignación de CP en logs de Central
5. Verificar inicio de sesión en base de datos

### Escenario 2: Monitorización por Socket

1. Ejecutar Engine en un terminal
2. Ejecutar Monitor en otro terminal
3. Observar consultas de estado cada 30 segundos por socket TCP
4. Verificar logs en ambos componentes

### Escenario 3: Eventos en Kafka

1. Iniciar todos los componentes
2. Realizar acciones (auth, request, etc.)
3. Observar eventos publicados en Kafka
4. Verificar Correlation IDs en los logs

## 📊 Base de Datos

### Esquema

**Tabla `users`**
- Usuarios del sistema (drivers y admins)
- Autenticación con password hash (SHA256)
- Balance de créditos

**Tabla `charging_points`**
- Puntos de carga registrados
- Estado actual y ubicación
- Tarifas por kWh

**Tabla `charging_sessions`**
- Sesiones de carga activas e históricas
- Energía consumida y costos calculados
- Correlation IDs para trazabilidad

**Tabla `event_log`**
- Log de eventos del sistema
- Auditoría completa
- Message IDs y timestamps

### Consultas Útiles

```bash
# Ejecutar Python en el directorio del proyecto
python

>>> import database as db
>>> db.get_available_charging_points()  # Ver CPs disponibles
>>> db.get_user_by_username('driver1')  # Ver datos de usuario
>>> db.get_user_sessions(1, limit=5)    # Historial de usuario
```

## 🔧 Configuración para Despliegue Distribuido

### Requisitos según PDF de la Práctica

Cada componente debe ejecutarse en un **PC distinto** en la misma red local:

- **PC 1**: EV_Driver (aplicaciones de conductores)
- **PC 2**: EV_Central + Kafka
- **PC 3**: EV_CP_E + EV_CP_M (Charging Points)

### Pasos para Despliegue

1. **Asignar IP fija** al PC donde corre Kafka y Central (ej: `192.168.1.100`)

2. **Editar `network_config.py`** en cada PC con las IPs reales:
   ```python
   CENTRAL_CONFIG = {'ip': '192.168.1.100', 'port': 5000}
   KAFKA_BROKER = '192.168.1.100:9092'
   ```

3. **Abrir puertos** en firewall:
   - Puerto 5000 (Central TCP)
   - Puerto 9000 (Engine TCP)
   - Puerto 9092 (Kafka)

4. **Verificar conectividad** entre PCs:
   ```bash
   ping 192.168.1.100
   telnet 192.168.1.100 9092
   ```

5. **Ejecutar componentes** en cada PC siguiendo el orden:
   - Primero: Kafka
   - Segundo: EV_Central
   - Tercero: EV_CP_E y EV_CP_M
   - Cuarto: EV_Driver

## 📝 Usuarios de Prueba

Creados automáticamente por `init_db.py`:

| Username | Password | Balance | Rol |
|----------|----------|---------|-----|
| driver1  | pass123  | €150.00 | driver |
| driver2  | pass456  | €200.00 | driver |
| admin    | admin123 | €0.00   | admin |

## 🐛 Troubleshooting

### Error: "No module named 'kafka'"
```bash
pip install kafka-python
```

### Error: "Connection refused" en Kafka
- Verificar que Kafka esté corriendo
- Comprobar IP y puerto en `network_config.py`
- Verificar firewall

### Error: "AUTH_FAILED"
- Verificar credenciales
- Ejecutar `python init_db.py` para recrear usuarios

### Error: Base de datos bloqueada
- Cerrar todos los procesos que usen la BD
- Eliminar `ev_charging.db` y ejecutar `init_db.py` de nuevo

## 📂 Estructura del Proyecto

```
SD/
├── database.py              # Módulo de base de datos SQLite
├── init_db.py              # Inicialización de BD
├── network_config.py       # Configuración de IPs
├── event_utils.py          # Utilidades para eventos
├── ev_charging.db          # Base de datos (generada)
├── EV_Central/
│   └── EV_Central.py       # Sistema central
├── EV_CP_E/
│   └── EV_CP_E.py         # Charging Point Engine
├── EV_CP_M/
│   └── EV_CP_M.py         # Charging Point Monitor
└── EV_Driver/
    └── EV_Driver.py        # Aplicación de conductor
```

## ✅ Características Implementadas

- ✅ **Autenticación de usuarios** con hash de contraseñas
- ✅ **Persistencia de datos** con SQLite
- ✅ **Comunicación por sockets TCP** entre componentes
- ✅ **Streaming de eventos con Kafka**
- ✅ **Correlation IDs** para trazabilidad
- ✅ **Gestión de sesiones de carga** con cálculo de costos
- ✅ **Monitorización en tiempo real** por sockets
- ✅ **Despliegue distribuido** en red local
- ✅ **Log de eventos** para auditoría

## 📖 Autor

Desarrollado para la práctica de Sistemas Distribuidos 2025  
Universidad de Alicante
