# � GUÍA COMPLETA DE DESPLIEGUE - Sistema de Carga de Vehículos Eléctricos

## 📋 Índice
1. [Requisitos del Sistema](#requisitos-del-sistema)
2. [Arquitectura de Despliegue](#arquitectura-de-despliegue)
3. [Instalación en PC1 - EV_Driver](#instalación-en-pc1---ev_driver)
4. [Instalación en PC2 - EV_Central + Kafka](#instalación-en-pc2---ev_central--kafka)
5. [Instalación en PC3 - EV_CP_M + EV_CP_E](#instalación-en-pc3---ev_cp_m--ev_cp_e)
6. [Configuración de Red](#configuración-de-red)
7. [Pruebas de Conectividad](#pruebas-de-conectividad)
8. [Arranque del Sistema](#arranque-del-sistema)
9. [Resolución de Problemas](#resolución-de-problemas)

---

## 📌 Requisitos del Sistema

### Hardware Mínimo (por PC)
- **Procesador**: Intel Core i3 o equivalente
- **RAM**: 4 GB (8 GB recomendado)
- **Disco**: 10 GB de espacio libre
- **Red**: Tarjeta de red Ethernet o WiFi (misma red local)

### Software Necesario
- **Windows 10/11** (o Linux/Mac con adaptaciones)
- **Python 3.11 o superior**
- **Apache Kafka 3.6+** (solo en PC2)
- **Navegador Web** (Chrome, Firefox, Edge)

---

## 🏗️ Arquitectura de Despliegue

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│      PC1        │         │      PC2        │         │      PC3        │
│   EV_Driver     │◄───────►│   EV_Central    │◄───────►│   EV_CP_M       │
│                 │         │   + Kafka       │         │   + EV_CP_E     │
│  WebSocket:8001 │         │  WebSocket:8002 │         │  WebSocket:8003 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
        │                           │                           │
        └───────────────────────────┴───────────────────────────┘
                          Red Local (LAN)
```

### Distribución de Componentes
- **PC1**: Interfaz de conductores (dashboard.html + EV_Driver)
- **PC2**: Servidor central + Kafka + Base de datos
- **PC3**: Monitor + Motor de simulación

---

## 🔧 Instalación en PC1 - EV_Driver

### Paso 1: Instalar Python

1. Descargar Python 3.11+ desde: https://www.python.org/downloads/
2. **IMPORTANTE**: Durante la instalación, marcar "Add Python to PATH"
3. Verificar instalación:
```powershell
python --version
# Debería mostrar: Python 3.11.x
```

### Paso 2: Copiar Archivos del Proyecto

**Opción A: Con Git**
```powershell
cd C:\Users\TuUsuario\Desktop
git clone <URL_REPOSITORIO> SD
cd SD
```

**Opción B: Copia Manual**
1. Crear carpeta: `C:\SD\`
2. Copiar estos archivos desde PC original:
   - `database.py`
   - `event_utils.py`
   - `network_config.py`
   - `requirements.txt`
   - `ev_charging.db` (base de datos)
   - Carpeta completa: `EV_Driver\`

**Estructura mínima requerida en PC1:**
```
C:\SD\
├── database.py
├── event_utils.py
├── network_config.py
├── requirements.txt
├── ev_charging.db
└── EV_Driver\
    ├── EV_Driver.py
    ├── EV_Driver_WebSocket.py
    └── dashboard.html
```

### Paso 3: Crear Entorno Virtual

```powershell
cd C:\SD
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Si da error de permisos, ejecutar primero:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Paso 4: Instalar Dependencias

```powershell
# Con el entorno virtual activado (.venv):
pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 5: Configurar Red (ver sección [Configuración de Red](#configuración-de-red))

---

## 🔧 Instalación en PC2 - EV_Central + Kafka

### Paso 1: Instalar Python (igual que PC1)

### Paso 2: Copiar Archivos del Proyecto

**Estructura mínima requerida en PC2:**
```
C:\SD\
├── database.py
├── event_utils.py
├── network_config.py
├── requirements.txt
├── ev_charging.db
├── init_db.py
└── EV_Central\
    ├── EV_Central.py
    ├── EV_Central_WebSocket.py
    └── admin_dashboard.html
```

### Paso 3: Crear Entorno Virtual e Instalar Dependencias (igual que PC1)

### Paso 4: Instalar y Configurar Apache Kafka

#### 4.1. Instalar Java (Kafka requiere Java)
1. Descargar OpenJDK 11+ desde: https://adoptium.net/
2. Instalar y verificar:
```powershell
java -version
# Debería mostrar: openjdk version "11" o superior
```

#### 4.2. Descargar Apache Kafka
1. Ir a: https://kafka.apache.org/downloads
2. Descargar **Scala 2.13 - kafka_2.13-3.6.1.tgz**
3. Extraer en: `C:\kafka\`

**Estructura de Kafka:**
```
C:\kafka\
├── bin\
│   └── windows\
│       ├── kafka-server-start.bat
│       └── zookeeper-server-start.bat
└── config\
    ├── kraft\
    │   └── server.properties
    └── server.properties
```

#### 4.3. Configurar Kafka en Modo KRaft (sin Zookeeper)

**Opción 1: Configuración Rápida**
```powershell
cd C:\kafka

# Generar UUID para cluster
.\bin\windows\kafka-storage.bat random-uuid
# Copiar el UUID generado (ej: J7s9-K3dL-M5nP-R8tV-W2xZ-A4bC-D6eF-G8hI)

# Formatear el directorio de logs
.\bin\windows\kafka-storage.bat format -t <UUID_COPIADO> -c .\config\kraft\server.properties

# Iniciar Kafka
.\bin\windows\kafka-server-start.bat .\config\kraft\server.properties
```

**Opción 2: Configuración con Zookeeper (alternativa)**
```powershell
# Terminal 1 - Iniciar Zookeeper
cd C:\kafka
.\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties

# Terminal 2 - Iniciar Kafka
cd C:\kafka
.\bin\windows\kafka-server-start.bat .\config\server.properties
```

#### 4.4. Crear Topics de Kafka
```powershell
cd C:\kafka

# Crear topic para eventos
.\bin\windows\kafka-topics.bat --create --topic ev-charging-events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1

# Verificar que se creó
.\bin\windows\kafka-topics.bat --list --bootstrap-server localhost:9092
```

#### 4.5. Configurar Kafka como Servicio de Windows (OPCIONAL)

Para que Kafka inicie automáticamente:

1. Descargar NSSM: https://nssm.cc/download
2. Ejecutar como Administrador:
```powershell
cd C:\nssm\win64

# Instalar Kafka como servicio
.\nssm.exe install Kafka "C:\kafka\bin\windows\kafka-server-start.bat" "C:\kafka\config\kraft\server.properties"

# Iniciar servicio
.\nssm.exe start Kafka
```

### Paso 5: Inicializar Base de Datos

```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python init_db.py
```

Esto creará:
- 12 usuarios (user01 a user12, contraseña: "password")
- 10 puntos de carga (CP001 a CP010)
- 18 sesiones de ejemplo

---

## 🔧 Instalación en PC3 - EV_CP_M + EV_CP_E

### Paso 1: Instalar Python (igual que PC1)

### Paso 2: Copiar Archivos del Proyecto

**Estructura mínima requerida en PC3:**
```
C:\SD\
├── database.py
├── event_utils.py
├── network_config.py
├── requirements.txt
├── ev_charging.db
├── EV_CP_M\
│   ├── EV_CP_M.py
│   ├── EV_CP_M_WebSocket.py
│   └── monitor_dashboard.html
└── EV_CP_E\
    └── EV_CP_E.py
```

### Paso 3: Crear Entorno Virtual e Instalar Dependencias (igual que PC1)

---

## 🌐 Configuración de Red

### Obtener Direcciones IP de cada PC

En cada PC, abrir PowerShell y ejecutar:
```powershell
ipconfig
```

Buscar la dirección IPv4 de la red local (ej: 192.168.1.xxx)

**Ejemplo:**
- PC1 (Driver): 192.168.1.101
- PC2 (Central): 192.168.1.102
- PC3 (Monitor): 192.168.1.103

### Modificar `network_config.py` en TODOS los PCs

Editar el archivo `C:\SD\network_config.py` con las IPs reales:

```python
# network_config.py - CONFIGURACIÓN ADAPTADA A TU RED

# ============================================
# DIRECCIONES IP DE LOS COMPONENTES
# ============================================

# PC1 - EV Driver (Interfaz de Conductores)
DRIVER_HOST = "192.168.1.101"  # IP de PC1
DRIVER_PORT = 5001
DRIVER_WS_PORT = 8001  # Puerto WebSocket

# PC2 - EV Central (Servidor Central + Kafka)
CENTRAL_HOST = "192.168.1.102"  # IP de PC2
CENTRAL_PORT = 5002
CENTRAL_WS_PORT = 8002  # Puerto WebSocket

# PC3 - Charging Point Monitor (Monitor)
CP_MONITOR_HOST = "192.168.1.103"  # IP de PC3
CP_MONITOR_PORT = 5003
CP_MONITOR_WS_PORT = 8003  # Puerto WebSocket

# PC3 - Charging Point Engine (Motor de Simulación)
CP_ENGINE_HOST = "192.168.1.103"  # IP de PC3 (mismo que monitor)
CP_ENGINE_PORT = 5004

# Kafka (en PC2)
KAFKA_HOST = "192.168.1.102"  # IP de PC2
KAFKA_PORT = 9092
KAFKA_TOPIC = "ev-charging-events"

# ============================================
# HOSTS COMPILADOS
# ============================================
DRIVER_FULL = f"{DRIVER_HOST}:{DRIVER_PORT}"
CENTRAL_FULL = f"{CENTRAL_HOST}:{CENTRAL_PORT}"
CP_MONITOR_FULL = f"{CP_MONITOR_HOST}:{CP_MONITOR_PORT}"
CP_ENGINE_FULL = f"{CP_ENGINE_HOST}:{CP_ENGINE_PORT}"
KAFKA_FULL = f"{KAFKA_HOST}:{KAFKA_PORT}"
```

**⚠️ IMPORTANTE**: Este archivo debe tener las MISMAS direcciones IP en los 3 PCs.

### Actualizar URLs de WebSocket en HTML

#### En PC1: Editar `EV_Driver\dashboard.html`
```javascript
// Línea ~30
const ws = new WebSocket('ws://192.168.1.101:8001/ws');  // IP de PC1
```

#### En PC2: Editar `EV_Central\admin_dashboard.html`
```javascript
// Línea ~50
const ws = new WebSocket('ws://192.168.1.102:8002/ws');  // IP de PC2
```

#### En PC3: Editar `EV_CP_M\monitor_dashboard.html`
```javascript
// Línea ~40
const ws = new WebSocket('ws://192.168.1.103:8003/ws');  // IP de PC3
```

### Configurar Firewall de Windows

En **CADA PC**, abrir PowerShell como **Administrador** y ejecutar:

**En PC1:**
```powershell
# Permitir puerto WebSocket del Driver
New-NetFirewallRule -DisplayName "EV_Driver WebSocket" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_Driver TCP" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
```

**En PC2:**
```powershell
# Permitir puerto WebSocket del Central
New-NetFirewallRule -DisplayName "EV_Central WebSocket" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_Central TCP" -Direction Inbound -LocalPort 5002 -Protocol TCP -Action Allow

# Permitir Kafka
New-NetFirewallRule -DisplayName "Apache Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
```

**En PC3:**
```powershell
# Permitir puerto WebSocket del Monitor
New-NetFirewallRule -DisplayName "EV_CP_M WebSocket" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_CP_M TCP" -Direction Inbound -LocalPort 5003 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_CP_E TCP" -Direction Inbound -LocalPort 5004 -Protocol TCP -Action Allow
```

---

## ✅ Pruebas de Conectividad

### Desde PC1 (Driver), probar conexión a PC2:
```powershell
# Probar TCP
Test-NetConnection -ComputerName 192.168.1.102 -Port 5002

# Probar Kafka
Test-NetConnection -ComputerName 192.168.1.102 -Port 9092
```

### Desde PC1, probar conexión a PC3:
```powershell
Test-NetConnection -ComputerName 192.168.1.103 -Port 5003
```

### Probar conectividad completa:
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python test_connections.py
```

**Resultado esperado:**
```
✓ Conexión a EV_Central (192.168.1.102:5002) exitosa
✓ Conexión a Kafka (192.168.1.102:9092) exitosa
✓ Conexión a EV_CP_M (192.168.1.103:5003) exitosa
✓ Conexión a EV_CP_E (192.168.1.103:5004) exitosa
```

---

## 🚀 Arranque del Sistema

### 🔴 ORDEN DE ARRANQUE (IMPORTANTE)

#### 1. Primero en PC2 - Iniciar Kafka
```powershell
cd C:\kafka
.\bin\windows\kafka-server-start.bat .\config\kraft\server.properties

# Esperar a ver: "Kafka Server started"
```

#### 2. Luego en PC2 - Iniciar EV_Central
```powershell
# Nueva terminal
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_Central\EV_Central_WebSocket.py
```

#### 3. En PC3 - Iniciar EV_CP_E (Motor)
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_CP_E\EV_CP_E.py
```

#### 4. En PC3 - Iniciar EV_CP_M (Monitor)
```powershell
# Nueva terminal en PC3
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_CP_M\EV_CP_M_WebSocket.py
```

#### 5. En PC1 - Iniciar EV_Driver
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_Driver\EV_Driver_WebSocket.py
```

### 📱 Abrir Interfaces Web

**Desde PC1:**
- Driver Dashboard: http://192.168.1.101:8001

**Desde PC2:**
- Admin Dashboard: http://192.168.1.102:8002

**Desde PC3:**
- Monitor Dashboard: http://192.168.1.103:8003

**Desde CUALQUIER PC en la red:**
- Driver: http://192.168.1.101:8001
- Admin: http://192.168.1.102:8002
- Monitor: http://192.168.1.103:8003

---

## 🔧 Resolución de Problemas

### Error: "No se puede conectar al servidor WebSocket"

**Causa**: Firewall bloqueando puerto o servidor no iniciado

**Solución**:
1. Verificar que el servidor está corriendo
2. Verificar firewall:
```powershell
Get-NetFirewallRule -DisplayName "EV_*"
```
3. Verificar IP correcta en `network_config.py`

### Error: "kafka.errors.NoBrokersAvailable"

**Causa**: Kafka no está corriendo o no es accesible

**Solución**:
1. En PC2, verificar que Kafka está corriendo:
```powershell
netstat -ano | findstr 9092
```
2. Reiniciar Kafka si es necesario
3. Verificar firewall del puerto 9092

### Error: "OSError: [WinError 10048] Only one usage of each socket address"

**Causa**: Puerto ya en uso por otro proceso

**Solución**:
```powershell
# Ver qué proceso usa el puerto (ej: 8001)
netstat -ano | findstr :8001

# Matar el proceso (reemplazar <PID> con el número mostrado)
taskkill /PID <PID> /F
```

### Error: "ModuleNotFoundError: No module named 'websockets'"

**Causa**: Dependencias no instaladas o entorno virtual no activado

**Solución**:
```powershell
# Activar entorno virtual
.\.venv\Scripts\Activate.ps1

# Reinstalar dependencias
pip install -r requirements.txt
```

### Las interfaces web no se actualizan en tiempo real

**Causa**: WebSocket desconectado

**Solución**:
1. Abrir consola del navegador (F12)
2. Verificar errores de WebSocket
3. Revisar que la URL del WebSocket es correcta (IP + puerto)
4. Reiniciar el servidor correspondiente

### Base de datos vacía o sin datos

**Solución**:
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python init_db.py
```

---

## 📦 Checklist de Despliegue

### ✅ PC1 - EV_Driver
- [ ] Python 3.11+ instalado
- [ ] Carpeta `C:\SD\` con archivos necesarios
- [ ] Entorno virtual creado
- [ ] Dependencias instaladas (`pip install -r requirements.txt`)
- [ ] `network_config.py` editado con IPs correctas
- [ ] `dashboard.html` editado con IP correcta de WebSocket
- [ ] Firewall configurado (puerto 8001)
- [ ] Base de datos `ev_charging.db` copiada

### ✅ PC2 - EV_Central + Kafka
- [ ] Python 3.11+ instalado
- [ ] Java JDK 11+ instalado
- [ ] Kafka descargado y extraído en `C:\kafka\`
- [ ] Kafka formateado con UUID
- [ ] Topic `ev-charging-events` creado
- [ ] Carpeta `C:\SD\` con archivos necesarios
- [ ] Entorno virtual creado
- [ ] Dependencias instaladas
- [ ] `network_config.py` editado con IPs correctas
- [ ] `admin_dashboard.html` editado con IP correcta
- [ ] Firewall configurado (puertos 8002, 9092)
- [ ] Base de datos inicializada (`python init_db.py`)

### ✅ PC3 - EV_CP_M + EV_CP_E
- [ ] Python 3.11+ instalado
- [ ] Carpeta `C:\SD\` con archivos necesarios
- [ ] Entorno virtual creado
- [ ] Dependencias instaladas
- [ ] `network_config.py` editado con IPs correctas
- [ ] `monitor_dashboard.html` editado con IP correcta
- [ ] Firewall configurado (puertos 8003, 5003, 5004)
- [ ] Base de datos `ev_charging.db` copiada

### ✅ Red y Conectividad
- [ ] Todos los PCs en la misma red local
- [ ] IPs obtenidas y documentadas
- [ ] Pruebas de conectividad exitosas (`test_connections.py`)
- [ ] Firewall configurado en los 3 PCs

---

## 📞 Soporte Adicional

### Logs para Debug

En cada servidor, los logs se muestran en la consola. Guardar en archivo:
```powershell
python EV_Driver\EV_Driver_WebSocket.py > driver_log.txt 2>&1
```

### Comandos Útiles

```powershell
# Ver puertos en uso
netstat -ano | findstr LISTEN

# Ver procesos Python
tasklist | findstr python

# Reiniciar servicio de Kafka (si se instaló como servicio)
nssm restart Kafka
```

---

## 🎓 Notas Finales

1. **Copiar la base de datos**: Asegúrate de copiar `ev_charging.db` a los 3 PCs después de inicializarla en PC2

2. **Sincronizar configuración**: El archivo `network_config.py` debe ser idéntico en los 3 PCs

3. **Orden de arranque**: Respetar siempre el orden: Kafka → Central → Engine → Monitor → Driver

4. **Usuarios de prueba**: 
   - Usuario: `user01` a `user12`
   - Contraseña: `password`
   - Saldos: entre 50.00 y 150.00€

5. **Apagar el sistema**: Usar `Ctrl+C` en cada terminal, en orden inverso al arranque

---

**¡Sistema listo para demostración distribuida en 3 PCs!** 🎉

**Modo interactivo (con simulación de fallos):**
```bash
python EV_CP_E/EV_CP_E.py --interactive
```

### 🎮 **Simulación Interactiva del Motor (EV_CP_E)**

Una vez ejecutado en modo `--interactive`, podrás:

- **Tecla 'K' + ENTER**: Simular fallo del motor (estado KO) 🔴
- **Tecla 'O' + ENTER**: Restaurar funcionamiento normal (estado OK) 🟢  
- **Tecla 'Q' + ENTER**: Salir de la simulación ❌

Durante un fallo simulado:
- El motor no puede iniciar nuevas cargas
- Las cargas en curso se detienen automáticamente
- Los eventos se publican en Kafka para monitoreo
python EV_CP_E/EV_CP_E.py
```

## 🔧 Configuración de Firewall

**EN TODOS LOS PCs**, asegúrate de que el puerto 5000 esté abierto:

### Windows Defender Firewall:
1. Panel de Control → Sistema y seguridad → Firewall de Windows Defender
2. Configuración avanzada → Reglas de entrada → Nueva regla
3. Puerto → TCP → Puerto específico: 5000
4. Permitir la conexión
5. Aplicar a todos los perfiles

## 🧪 Pruebas

### Prueba de Conectividad:
Desde PC1 y PC3, prueba si puedes hacer ping al servidor:
```bash
ping 192.168.1.227
```

### Orden de Ejecución:
1. **PC2**: Ejecutar EV_Central
2. **PC1**: Ejecutar EV_Driver  
3. **PC3**: Ejecutar EV_CP_M y EV_CP_E

## 📱 Contacto entre Componentes

- **EV_Driver** (PC1) → **EV_Central** (PC2)
- **EV_CP_M** (PC3) → **EV_Central** (PC2)  
- **EV_CP_E** (PC3) → **EV_Central** (PC2)

## � Kafka Topics y Trazabilidad

- Topics activos:
	- driver-events, central-events, cp-events (cp-events unifica Monitor y Engine)
- Cada mensaje incluye:
	- message_id (único por evento)
	- correlation_id (misma sesión/conversación)
	- key de Kafka por entidad (driver_id/cp_id/engine_id) para mantener el orden por clave

## �🐛 Solución de Problemas

### Error "Connection Refused":
- Verificar que EV_Central está ejecutándose
- Comprobar IPs en network_config.py
- Verificar firewall/puertos

### Error "Network Unreachable":
- Verificar que todos los PCs están en la misma red
- Probar conectividad con ping

### Error "Import network_config":
- Verificar que network_config.py está en la carpeta raíz del proyecto
- Verificar que las IPs están configuradas correctamente