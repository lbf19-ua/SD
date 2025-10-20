# 🚀 GUÍA RÁPIDA DE 10 PASOS - Despliegue EV Charging

## 📍 Despliegue en 3 PCs: PC1 (Driver) | PC2 (Central+Kafka) | PC3 (Monitor)

---

## 🔟 10 PASOS PARA DESPLEGAR EL SISTEMA

### **PASO 1**: Instalar Python en los 3 PCs ⏱️ 15 min
```powershell
# Descargar: https://www.python.org/downloads/
# ✅ Marcar: "Add Python to PATH"
# Verificar:
python --version
```

### **PASO 2**: Instalar Java en PC2 (solo PC2) ⏱️ 10 min
```powershell
# Descargar: https://adoptium.net/
# Versión: OpenJDK 11 o superior
# Verificar:
java -version
```

### **PASO 3**: Instalar Kafka en PC2 (solo PC2) ⏱️ 20 min
```powershell
# Descargar: https://kafka.apache.org/downloads
# Extraer en: C:\kafka\
# Generar UUID:
cd C:\kafka
.\bin\windows\kafka-storage.bat random-uuid

# Formatear (usar UUID generado):
.\bin\windows\kafka-storage.bat format -t <UUID> -c .\config\kraft\server.properties

# Crear topic:
.\bin\windows\kafka-topics.bat --create --topic ev-charging-events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

### **PASO 4**: Copiar archivos del proyecto a cada PC ⏱️ 15 min
```
PC1 necesita:  EV_Driver\ + archivos base
PC2 necesita:  EV_Central\ + archivos base + init_db.py
PC3 necesita:  EV_CP_M\ + EV_CP_E\ + archivos base

Archivos base (todos los PCs):
- database.py
- event_utils.py
- network_config.py
- requirements.txt
```

### **PASO 5**: Crear entornos virtuales ⏱️ 15 min
```powershell
# En cada PC, dentro de C:\SD\:
python -m venv .venv

# Activar (si da error, ejecutar primero el comando de abajo):
.\.venv\Scripts\Activate.ps1

# Si da error de permisos:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### **PASO 6**: Instalar dependencias Python ⏱️ 15 min
```powershell
# En cada PC (con .venv activado):
cd C:\SD
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### **PASO 7**: Obtener IPs y configurar red ⏱️ 20 min
```powershell
# En cada PC:
ipconfig
# Anotar la IPv4 (ej: 192.168.1.101)

# Editar C:\SD\network_config.py en TODOS los PCs:
DRIVER_HOST = "192.168.1.101"      # IP de PC1
CENTRAL_HOST = "192.168.1.102"     # IP de PC2
CP_MONITOR_HOST = "192.168.1.103"  # IP de PC3
KAFKA_HOST = "192.168.1.102"       # IP de PC2

# Editar archivos HTML:
# PC1: EV_Driver\dashboard.html - línea ~30
# PC2: EV_Central\admin_dashboard.html - línea ~50
# PC3: EV_CP_M\monitor_dashboard.html - línea ~40
# Cambiar: ws://localhost:800X/ws → ws://<IP_DEL_PC>:800X/ws
```

### **PASO 8**: Configurar Firewall ⏱️ 10 min
```powershell
# PC1 (como Administrador):
New-NetFirewallRule -DisplayName "EV_Driver WebSocket" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_Driver TCP" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow

# PC2 (como Administrador):
New-NetFirewallRule -DisplayName "EV_Central WebSocket" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_Central TCP" -Direction Inbound -LocalPort 5002 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Apache Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow

# PC3 (como Administrador):
New-NetFirewallRule -DisplayName "EV_CP_M WebSocket" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_CP_M TCP" -Direction Inbound -LocalPort 5003 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV_CP_E TCP" -Direction Inbound -LocalPort 5004 -Protocol TCP -Action Allow
```

### **PASO 9**: Inicializar base de datos (solo en PC2) ⏱️ 5 min
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python init_db.py
# ✅ Crea: 12 usuarios, 10 CPs, 18 sesiones

# Copiar ev_charging.db a PC1 y PC3
```

### **PASO 10**: Iniciar el sistema ⏱️ 5 min

#### 🟢 ORDEN DE ARRANQUE (IMPORTANTE):

**1️⃣ PC2 - Iniciar Kafka:**
```powershell
cd C:\kafka
.\bin\windows\kafka-server-start.bat .\config\kraft\server.properties
# Esperar: "Kafka Server started"
```

**2️⃣ PC2 - Iniciar Central (nueva terminal):**
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_Central\EV_Central_WebSocket.py
```

**3️⃣ PC3 - Iniciar Engine:**
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_CP_E\EV_CP_E.py
```

**4️⃣ PC3 - Iniciar Monitor (nueva terminal):**
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_CP_M\EV_CP_M_WebSocket.py
```

**5️⃣ PC1 - Iniciar Driver:**
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
python EV_Driver\EV_Driver_WebSocket.py
```

---

## 🌐 Acceder a las Interfaces

Desde cualquier navegador en la red local:

| Interfaz | URL | Usuario | Contraseña |
|----------|-----|---------|-----------|
| 🚗 **Driver** | http://192.168.1.101:8001 | user01 | password |
| 👨‍💼 **Admin** | http://192.168.1.102:8002 | - | - |
| 📊 **Monitor** | http://192.168.1.103:8003 | - | - |

*(Reemplazar IPs con las reales de tu red)*

---

## ✅ Verificación Rápida

### 1. Kafka corriendo en PC2:
```powershell
netstat -ano | findstr 9092
# Debe mostrar: LISTENING en puerto 9092
```

### 2. Servidores WebSocket activos:
- PC1: http://192.168.1.101:8001 → debe mostrar dashboard
- PC2: http://192.168.1.102:8002 → debe mostrar dashboard
- PC3: http://192.168.1.103:8003 → debe mostrar dashboard

### 3. Conectividad entre PCs:
```powershell
# Desde PC1:
Test-NetConnection -ComputerName 192.168.1.102 -Port 9092
Test-NetConnection -ComputerName 192.168.1.103 -Port 5003
```

---

## 🔧 Solución de Problemas Rápida

| Error | Solución |
|-------|----------|
| "python no reconocido" | Reinstalar Python con "Add to PATH" |
| "No module named websockets" | `.\.venv\Scripts\Activate.ps1` y `pip install -r requirements.txt` |
| "Port already in use" | `netstat -ano \| findstr :8001` → `taskkill /PID <PID> /F` |
| WebSocket no conecta | Verificar firewall y que servidor está corriendo |
| Kafka no disponible | Verificar que Kafka está corriendo en PC2 |

---

## 📋 Checklist Previo a Demostración

**PC1:**
- [ ] Python instalado
- [ ] Entorno virtual creado
- [ ] Dependencias instaladas
- [ ] `network_config.py` editado
- [ ] `dashboard.html` editado
- [ ] Firewall configurado
- [ ] `ev_charging.db` copiada

**PC2:**
- [ ] Python instalado
- [ ] Java instalado
- [ ] Kafka instalado y configurado
- [ ] Topic creado
- [ ] Entorno virtual creado
- [ ] Dependencias instaladas
- [ ] Base de datos inicializada
- [ ] `network_config.py` editado
- [ ] `admin_dashboard.html` editado
- [ ] Firewall configurado

**PC3:**
- [ ] Python instalado
- [ ] Entorno virtual creado
- [ ] Dependencias instaladas
- [ ] `network_config.py` editado
- [ ] `monitor_dashboard.html` editado
- [ ] Firewall configurado
- [ ] `ev_charging.db` copiada

**Red:**
- [ ] Los 3 PCs en la misma red local
- [ ] IPs obtenidas y documentadas
- [ ] Conectividad verificada

---

## 🎯 Comandos Esenciales

### Iniciar Sistema (orden correcto):
```powershell
# PC2 Terminal 1
cd C:\kafka; .\bin\windows\kafka-server-start.bat .\config\kraft\server.properties

# PC2 Terminal 2
cd C:\SD; .\.venv\Scripts\Activate.ps1; python EV_Central\EV_Central_WebSocket.py

# PC3 Terminal 1
cd C:\SD; .\.venv\Scripts\Activate.ps1; python EV_CP_E\EV_CP_E.py

# PC3 Terminal 2
cd C:\SD; .\.venv\Scripts\Activate.ps1; python EV_CP_M\EV_CP_M_WebSocket.py

# PC1
cd C:\SD; .\.venv\Scripts\Activate.ps1; python EV_Driver\EV_Driver_WebSocket.py
```

### Detener Sistema (Ctrl+C en cada terminal, orden inverso):
1. PC1: Driver
2. PC3: Monitor
3. PC3: Engine
4. PC2: Central
5. PC2: Kafka

---

## 📞 Ayuda Rápida

**Documentación completa**: Ver `DEPLOYMENT_GUIDE.md`

**Checklist detallado**: Ver `INSTALLATION_CHECKLIST.md`

**Descargas**: Ver `DOWNLOADS_GUIDE.md`

**Guía interfaces**: Ver `WEB_INTERFACES_README.md`

---

**Tiempo total estimado de instalación**: 2-3 horas

**¡Buena suerte con la demostración!** 🚀🎉
