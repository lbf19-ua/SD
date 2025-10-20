# 🚀 DESPLIEGUE LOCAL - Todos los Componentes en un Solo PC

## 📋 Requisitos
- ✅ Python 3.11+ con entorno virtual activado
- ✅ Apache Kafka instalado en `C:\kafka\`
- ✅ Dependencias Python instaladas

## 🎯 Objetivo
Ejecutar todo el sistema en **localhost** usando múltiples terminales para simular los 3 PCs.

---

## 📊 Configuración Local

### IPs y Puertos
Todos los componentes usan **localhost (127.0.0.1)** o **172.21.0.1**:

| Componente | Puerto TCP | Puerto WebSocket | Terminal |
|------------|-----------|------------------|----------|
| Kafka | 9092 | - | Terminal 1 |
| EV_Central | 5002 | 8002 | Terminal 2 |
| EV_CP_E (Engine) | 5004 | - | Terminal 3 |
| EV_CP_M (Monitor) | 5003 | 8003 | Terminal 4 |
| EV_Driver | 5001 | 8001 | Terminal 5 |

---

## 🔢 ORDEN DE ARRANQUE (Paso a Paso)

### ✅ PASO 1: Verificar Base de Datos
```powershell
cd C:\Users\luisb\Desktop\SD\SD
.\.venv\Scripts\Activate.ps1

# Si no existe ev_charging.db, inicializar:
python init_db.py
```

**Resultado esperado:**
- Base de datos creada con 12 usuarios, 10 CPs, 18 sesiones

---

### ✅ PASO 2: Iniciar Kafka (Terminal 1)

**Opción A: Modo KRaft (sin Zookeeper)**
```powershell
# Nueva terminal PowerShell
cd C:\kafka

# Si es la primera vez, generar UUID:
.\bin\windows\kafka-storage.bat random-uuid
# Ejemplo salida: J7s9-K3dL-M5nP-R8tV-W2xZ

# Formatear (solo primera vez, usar UUID de arriba):
.\bin\windows\kafka-storage.bat format -t <UUID_GENERADO> -c .\config\kraft\server.properties

# Iniciar Kafka
.\bin\windows\kafka-server-start.bat .\config\kraft\server.properties
```

**Opción B: Modo con Zookeeper**
```powershell
# Terminal 1a - Zookeeper
cd C:\kafka
.\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties

# Terminal 1b - Kafka (en otra terminal)
cd C:\kafka
.\bin\windows\kafka-server-start.bat .\config\server.properties
```

**Verificar que Kafka está corriendo:**
```powershell
# En otra terminal:
netstat -ano | findstr :9092
# Debe mostrar: LISTENING en puerto 9092
```

**Esperar a ver:**
```
[KafkaServer id=1] started (kafka.server.KafkaServer)
```

---

### ✅ PASO 3: Crear Topic de Kafka (solo primera vez)

```powershell
# Nueva terminal PowerShell
cd C:\kafka

# Crear topic
.\bin\windows\kafka-topics.bat --create --topic ev-charging-events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1

# Verificar
.\bin\windows\kafka-topics.bat --list --bootstrap-server localhost:9092
```

**Resultado esperado:**
```
Created topic ev-charging-events.
```

---

### ✅ PASO 4: Iniciar EV_Central (Terminal 2)

```powershell
# Nueva terminal PowerShell
cd C:\Users\luisb\Desktop\SD\SD
.\.venv\Scripts\Activate.ps1

# Iniciar servidor central con WebSocket
python EV_Central\EV_Central_WebSocket.py
```

**Resultado esperado:**
```
🏢 EV Central WebSocket Server
==============================
📊 HTTP Server: http://localhost:8002
🔌 WebSocket: ws://localhost:8002/ws
⚡ Kafka: localhost:9092 (topic: ev-charging-events)
🗄️ Database: ev_charging.db

[INFO] Admin dashboard disponible en: http://localhost:8002
[INFO] WebSocket escuchando en: ws://localhost:8002/ws
[INFO] Kafka consumer iniciado
```

---

### ✅ PASO 5: Iniciar EV_CP_E - Motor (Terminal 3)

```powershell
# Nueva terminal PowerShell
cd C:\Users\luisb\Desktop\SD\SD
.\.venv\Scripts\Activate.ps1

# Iniciar motor de simulación
python EV_CP_E\EV_CP_E.py
```

**Resultado esperado:**
```
⚙️ EV Charging Point Engine
===========================
📡 Escuchando en: localhost:5004
🔌 Kafka: localhost:9092
```

---

### ✅ PASO 6: Iniciar EV_CP_M - Monitor (Terminal 4)

```powershell
# Nueva terminal PowerShell
cd C:\Users\luisb\Desktop\SD\SD
.\.venv\Scripts\Activate.ps1

# Iniciar monitor con WebSocket
python EV_CP_M\EV_CP_M_WebSocket.py
```

**Resultado esperado:**
```
📊 EV Charging Point Monitor - WebSocket Server
================================================
📊 HTTP Server: http://localhost:8003
🔌 WebSocket: ws://localhost:8003/ws
🗄️ Database: ev_charging.db

[INFO] Monitor dashboard disponible en: http://localhost:8003
[INFO] WebSocket escuchando en: ws://localhost:8003/ws
```

---

### ✅ PASO 7: Iniciar EV_Driver (Terminal 5)

```powershell
# Nueva terminal PowerShell
cd C:\Users\luisb\Desktop\SD\SD
.\.venv\Scripts\Activate.ps1

# Iniciar driver con WebSocket
python EV_Driver\EV_Driver_WebSocket.py
```

**Resultado esperado:**
```
🚗 EV Driver WebSocket Server
==============================
📊 HTTP Server: http://localhost:8001
🔌 WebSocket: ws://localhost:8001/ws
🗄️ Database: ev_charging.db

[INFO] Driver dashboard disponible en: http://localhost:8001
[INFO] WebSocket escuchando en: ws://localhost:8001/ws
```

---

## 🌐 Acceder a las Interfaces Web

Una vez todos los servidores estén corriendo, abre tu navegador:

### 🚗 Dashboard de Conductores
- **URL**: http://localhost:8001
- **Login**: 
  - Usuario: `user01` (o user02, user03... hasta user12)
  - Contraseña: `password`
- **Funciones**:
  - Solicitar carga
  - Ver progreso en tiempo real
  - Parar carga
  - Ver saldo

### 👨‍💼 Dashboard de Administración
- **URL**: http://localhost:8002
- **Funciones**:
  - Ver estadísticas globales
  - Sesiones activas
  - Estado de todos los CPs
  - Lista de usuarios
  - Stream de eventos

### 📊 Dashboard de Monitorización
- **URL**: http://localhost:8003
- **Funciones**:
  - Grid de puntos de carga
  - Alertas del sistema
  - Gráficos de uso
  - Métricas detalladas

---

## ✅ Verificación del Sistema

### 1. Verificar que todos los puertos están escuchando:
```powershell
netstat -ano | findstr "8001 8002 8003 9092"
```

**Resultado esperado:**
```
TCP    0.0.0.0:8001    LISTENING
TCP    0.0.0.0:8002    LISTENING
TCP    0.0.0.0:8003    LISTENING
TCP    0.0.0.0:9092    LISTENING
```

### 2. Verificar procesos Python:
```powershell
tasklist | findstr python
```

**Resultado esperado:** Varios procesos `python.exe`

### 3. Probar las interfaces web:
- ✅ http://localhost:8001 → Dashboard Driver
- ✅ http://localhost:8002 → Dashboard Admin
- ✅ http://localhost:8003 → Dashboard Monitor

---

## 🧪 Prueba Funcional Completa

### 1. Login en Dashboard Driver
1. Ir a: http://localhost:8001
2. Usuario: `user01`
3. Contraseña: `password`
4. Click en "Login"

### 2. Solicitar Carga
1. Click en botón "🔌 Solicitar Carga"
2. Observar:
   - ✅ Mensaje de confirmación
   - ✅ Progreso aparece
   - ✅ Energía y coste actualizándose
   - ✅ Log de eventos

### 3. Verificar en Dashboard Admin
1. Ir a: http://localhost:8002
2. Observar:
   - ✅ Sesión activa en tabla
   - ✅ Estadísticas actualizadas
   - ✅ Eventos apareciendo en stream

### 4. Verificar en Dashboard Monitor
1. Ir a: http://localhost:8003
2. Observar:
   - ✅ CP asignado muestra "En Uso"
   - ✅ Gráfico actualizado
   - ✅ Métricas cambiando

### 5. Parar Carga
1. Volver a http://localhost:8001
2. Click en "⏹️ Parar Carga"
3. Observar:
   - ✅ Sesión finalizada
   - ✅ Coste total calculado
   - ✅ Saldo actualizado

---

## 🛑 Apagar el Sistema

**IMPORTANTE**: Apagar en orden inverso al arranque

### 1. Terminal 5 - EV_Driver
```
Ctrl + C
```

### 2. Terminal 4 - EV_CP_M
```
Ctrl + C
```

### 3. Terminal 3 - EV_CP_E
```
Ctrl + C
```

### 4. Terminal 2 - EV_Central
```
Ctrl + C
```

### 5. Terminal 1 - Kafka
```
Ctrl + C
```

---

## 🔧 Solución de Problemas

### Error: "Address already in use" (Puerto ocupado)
```powershell
# Ver qué usa el puerto
netstat -ano | findstr :8001

# Matar el proceso (reemplazar <PID>)
taskkill /PID <PID> /F
```

### Error: "No se puede conectar a Kafka"
1. Verificar que Kafka está corriendo:
   ```powershell
   netstat -ano | findstr :9092
   ```
2. Reiniciar Kafka si es necesario

### Error: "ModuleNotFoundError: No module named 'websockets'"
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Error: "Database is locked"
1. Cerrar todos los procesos Python
2. Reiniciar en orden correcto

### WebSocket no conecta
1. Abrir consola del navegador (F12)
2. Verificar URL del WebSocket
3. Reiniciar el servidor correspondiente

---

## 📊 Resumen de Terminales Necesarias

```
┌─────────────────────────────────────────────────────────────┐
│                    TU ORDENADOR (localhost)                 │
├─────────────────────────────────────────────────────────────┤
│  Terminal 1: Kafka (puerto 9092)                           │
│  Terminal 2: EV_Central (puerto 8002 WS + 5002 TCP)        │
│  Terminal 3: EV_CP_E (puerto 5004 TCP)                     │
│  Terminal 4: EV_CP_M (puerto 8003 WS + 5003 TCP)           │
│  Terminal 5: EV_Driver (puerto 8001 WS + 5001 TCP)         │
│                                                             │
│  Navegador: http://localhost:8001 (Driver)                 │
│             http://localhost:8002 (Admin)                  │
│             http://localhost:8003 (Monitor)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Comandos Rápidos (Copiar y Pegar)

### Terminal 1 - Kafka
```powershell
cd C:\kafka
.\bin\windows\kafka-server-start.bat .\config\kraft\server.properties
```

### Terminal 2 - Central
```powershell
cd C:\Users\luisb\Desktop\SD\SD ; .\.venv\Scripts\Activate.ps1 ; python EV_Central\EV_Central_WebSocket.py
```

### Terminal 3 - Engine
```powershell
cd C:\Users\luisb\Desktop\SD\SD ; .\.venv\Scripts\Activate.ps1 ; python EV_CP_E\EV_CP_E.py
```

### Terminal 4 - Monitor
```powershell
cd C:\Users\luisb\Desktop\SD\SD ; .\.venv\Scripts\Activate.ps1 ; python EV_CP_M\EV_CP_M_WebSocket.py
```

### Terminal 5 - Driver
```powershell
cd C:\Users\luisb\Desktop\SD\SD ; .\.venv\Scripts\Activate.ps1 ; python EV_Driver\EV_Driver_WebSocket.py
```

---

## ✅ Checklist Pre-Arranque

- [ ] Base de datos inicializada (`ev_charging.db` existe)
- [ ] Kafka instalado en `C:\kafka\`
- [ ] Entorno virtual activado
- [ ] Dependencias instaladas
- [ ] 5 terminales PowerShell abiertas
- [ ] Navegador listo

---

**¡Todo listo para arrancar el sistema en local!** 🚀

**Tiempo estimado de arranque**: 5-10 minutos
