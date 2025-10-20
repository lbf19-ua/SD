# ✅ CHECKLIST DE INSTALACIÓN - Sistema EV Charging

## 📋 Lista de Verificación Rápida

---

## 🖥️ PC1 - EV_Driver (Interfaz de Conductores)

### Instalación Base
- [ ] Windows 10/11 instalado
- [ ] Python 3.11+ instalado y en PATH
  - Verificar: `python --version`
- [ ] Carpeta `C:\SD\` creada

### Archivos Necesarios
- [ ] `database.py`
- [ ] `event_utils.py`
- [ ] `network_config.py`
- [ ] `requirements.txt`
- [ ] `ev_charging.db`
- [ ] Carpeta `EV_Driver\` completa
  - [ ] `EV_Driver.py`
  - [ ] `EV_Driver_WebSocket.py`
  - [ ] `dashboard.html`

### Configuración Python
- [ ] Entorno virtual creado: `python -m venv .venv`
- [ ] Entorno activado: `.\.venv\Scripts\Activate.ps1`
- [ ] Dependencias instaladas: `pip install -r requirements.txt`
- [ ] Verificar instalación:
  - [ ] `websockets` instalado
  - [ ] `aiohttp` instalado
  - [ ] `kafka-python` instalado

### Configuración de Red
- [ ] IP obtenida: _________________ (anotar aquí)
- [ ] `network_config.py` editado:
  - [ ] `DRIVER_HOST` = IP de este PC
  - [ ] `CENTRAL_HOST` = IP de PC2
  - [ ] `CP_MONITOR_HOST` = IP de PC3
  - [ ] `KAFKA_HOST` = IP de PC2
- [ ] `dashboard.html` editado:
  - [ ] WebSocket URL actualizada (línea ~30)
  - [ ] `ws://<IP_PC1>:8001/ws`

### Firewall
- [ ] Puerto 8001 permitido:
  ```powershell
  New-NetFirewallRule -DisplayName "EV_Driver WebSocket" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
  ```
- [ ] Puerto 5001 permitido:
  ```powershell
  New-NetFirewallRule -DisplayName "EV_Driver TCP" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
  ```

### Prueba
- [ ] Servidor inicia: `python EV_Driver\EV_Driver_WebSocket.py`
- [ ] Dashboard accesible: http://<IP_PC1>:8001
- [ ] WebSocket conecta correctamente

---

## 🖥️ PC2 - EV_Central + Kafka (Servidor Central)

### Instalación Base
- [ ] Windows 10/11 instalado
- [ ] Python 3.11+ instalado y en PATH
- [ ] Java JDK 11+ instalado
  - Verificar: `java -version`
- [ ] Carpeta `C:\SD\` creada
- [ ] Carpeta `C:\kafka\` creada

### Archivos Necesarios
- [ ] `database.py`
- [ ] `event_utils.py`
- [ ] `network_config.py`
- [ ] `requirements.txt`
- [ ] `init_db.py`
- [ ] Carpeta `EV_Central\` completa
  - [ ] `EV_Central.py`
  - [ ] `EV_Central_WebSocket.py`
  - [ ] `admin_dashboard.html`

### Configuración Python
- [ ] Entorno virtual creado
- [ ] Entorno activado
- [ ] Dependencias instaladas
- [ ] Base de datos inicializada: `python init_db.py`
  - [ ] 12 usuarios creados
  - [ ] 10 puntos de carga creados
  - [ ] 18 sesiones de ejemplo

### Instalación Kafka
- [ ] Kafka descargado desde https://kafka.apache.org/downloads
- [ ] Kafka extraído en `C:\kafka\`
- [ ] UUID generado: _________________ (anotar)
  ```powershell
  cd C:\kafka
  .\bin\windows\kafka-storage.bat random-uuid
  ```
- [ ] Kafka formateado:
  ```powershell
  .\bin\windows\kafka-storage.bat format -t <UUID> -c .\config\kraft\server.properties
  ```
- [ ] Topic creado:
  ```powershell
  .\bin\windows\kafka-topics.bat --create --topic ev-charging-events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
  ```
- [ ] Topic verificado:
  ```powershell
  .\bin\windows\kafka-topics.bat --list --bootstrap-server localhost:9092
  ```

### Configuración de Red
- [ ] IP obtenida: _________________ (anotar aquí)
- [ ] `network_config.py` editado (mismas IPs que PC1)
- [ ] `admin_dashboard.html` editado:
  - [ ] WebSocket URL actualizada (línea ~50)
  - [ ] `ws://<IP_PC2>:8002/ws`

### Firewall
- [ ] Puerto 8002 permitido (WebSocket Central)
- [ ] Puerto 5002 permitido (TCP Central)
- [ ] Puerto 9092 permitido (Kafka):
  ```powershell
  New-NetFirewallRule -DisplayName "Apache Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
  ```

### Prueba
- [ ] Kafka inicia: `.\bin\windows\kafka-server-start.bat .\config\kraft\server.properties`
- [ ] Mensaje "Kafka Server started" visible
- [ ] Servidor Central inicia: `python EV_Central\EV_Central_WebSocket.py`
- [ ] Dashboard accesible: http://<IP_PC2>:8002

---

## 🖥️ PC3 - EV_CP_M + EV_CP_E (Monitor y Motor)

### Instalación Base
- [ ] Windows 10/11 instalado
- [ ] Python 3.11+ instalado y en PATH
- [ ] Carpeta `C:\SD\` creada

### Archivos Necesarios
- [ ] `database.py`
- [ ] `event_utils.py`
- [ ] `network_config.py`
- [ ] `requirements.txt`
- [ ] `ev_charging.db` (copiada desde PC2)
- [ ] Carpeta `EV_CP_M\` completa
  - [ ] `EV_CP_M.py`
  - [ ] `EV_CP_M_WebSocket.py`
  - [ ] `monitor_dashboard.html`
- [ ] Carpeta `EV_CP_E\` completa
  - [ ] `EV_CP_E.py`

### Configuración Python
- [ ] Entorno virtual creado
- [ ] Entorno activado
- [ ] Dependencias instaladas

### Configuración de Red
- [ ] IP obtenida: _________________ (anotar aquí)
- [ ] `network_config.py` editado (mismas IPs que PC1 y PC2)
- [ ] `monitor_dashboard.html` editado:
  - [ ] WebSocket URL actualizada (línea ~40)
  - [ ] `ws://<IP_PC3>:8003/ws`

### Firewall
- [ ] Puerto 8003 permitido (WebSocket Monitor)
- [ ] Puerto 5003 permitido (TCP Monitor)
- [ ] Puerto 5004 permitido (TCP Engine):
  ```powershell
  New-NetFirewallRule -DisplayName "EV_CP_E TCP" -Direction Inbound -LocalPort 5004 -Protocol TCP -Action Allow
  ```

### Prueba
- [ ] Motor inicia: `python EV_CP_E\EV_CP_E.py`
- [ ] Monitor inicia: `python EV_CP_M\EV_CP_M_WebSocket.py`
- [ ] Dashboard accesible: http://<IP_PC3>:8003

---

## 🌐 Configuración Global de Red

### IPs Documentadas
| PC | Componente | IP | Puerto WS | Puerto TCP |
|----|------------|----|-----------| -----------|
| PC1 | EV_Driver | _______ | 8001 | 5001 |
| PC2 | EV_Central | _______ | 8002 | 5002 |
| PC2 | Kafka | _______ | - | 9092 |
| PC3 | EV_CP_M | _______ | 8003 | 5003 |
| PC3 | EV_CP_E | _______ | - | 5004 |

### Pruebas de Conectividad
Desde PC1:
- [ ] Ping a PC2: `ping <IP_PC2>`
- [ ] Ping a PC3: `ping <IP_PC3>`
- [ ] Conexión TCP a PC2:5002: `Test-NetConnection -ComputerName <IP_PC2> -Port 5002`
- [ ] Conexión Kafka a PC2:9092: `Test-NetConnection -ComputerName <IP_PC2> -Port 9092`
- [ ] Conexión TCP a PC3:5003: `Test-NetConnection -ComputerName <IP_PC3> -Port 5003`

Desde PC2:
- [ ] Ping a PC1
- [ ] Ping a PC3
- [ ] Conexión TCP a PC1:5001
- [ ] Conexión TCP a PC3:5004

Desde PC3:
- [ ] Ping a PC1
- [ ] Ping a PC2
- [ ] Conexión Kafka a PC2:9092

### Script de Prueba
- [ ] `test_connections.py` ejecutado en cada PC
- [ ] Todas las conexiones exitosas

---

## 🚀 Verificación Final

### Orden de Arranque
1. [ ] **PC2**: Kafka iniciado
2. [ ] **PC2**: EV_Central iniciado
3. [ ] **PC3**: EV_CP_E (Motor) iniciado
4. [ ] **PC3**: EV_CP_M (Monitor) iniciado
5. [ ] **PC1**: EV_Driver iniciado

### Acceso a Interfaces
- [ ] Dashboard Driver funciona: http://<IP_PC1>:8001
- [ ] Dashboard Admin funciona: http://<IP_PC2>:8002
- [ ] Dashboard Monitor funciona: http://<IP_PC3>:8003
- [ ] WebSockets conectados en las 3 interfaces
- [ ] Datos en tiempo real actualizándose

### Prueba Funcional
- [ ] Login exitoso en Dashboard Driver (user01/password)
- [ ] Solicitar carga funciona
- [ ] Eventos aparecen en Dashboard Admin
- [ ] Estado de CP actualizado en Dashboard Monitor
- [ ] Detener carga funciona
- [ ] Saldo actualizado correctamente

---

## 🎯 Usuarios de Prueba

| Usuario | Contraseña | Saldo Inicial |
|---------|-----------|---------------|
| user01 | password | ~100€ |
| user02 | password | ~100€ |
| user03 | password | ~100€ |
| ... | password | ~100€ |
| user12 | password | ~100€ |

---

## 📁 Estructura de Archivos Requerida

```
C:\SD\
├── database.py
├── event_utils.py
├── network_config.py
├── requirements.txt
├── ev_charging.db
├── init_db.py
├── test_connections.py
├── EV_Driver\
│   ├── EV_Driver.py
│   ├── EV_Driver_WebSocket.py
│   └── dashboard.html
├── EV_Central\
│   ├── EV_Central.py
│   ├── EV_Central_WebSocket.py
│   └── admin_dashboard.html
├── EV_CP_M\
│   ├── EV_CP_M.py
│   ├── EV_CP_M_WebSocket.py
│   └── monitor_dashboard.html
└── EV_CP_E\
    └── EV_CP_E.py
```

---

## 🔧 Resolución Rápida de Errores

| Error | Solución Rápida |
|-------|----------------|
| "Python no reconocido" | Reinstalar Python marcando "Add to PATH" |
| "No module named 'websockets'" | Activar .venv y ejecutar `pip install -r requirements.txt` |
| "Port already in use" | Cerrar proceso: `taskkill /PID <PID> /F` |
| "No se puede conectar a WebSocket" | Verificar firewall y que servidor está corriendo |
| "kafka.errors.NoBrokersAvailable" | Verificar que Kafka está corriendo en PC2 |
| Interfaces no actualizan | Revisar consola del navegador (F12) |

---

**Notas:**
- Este checklist debe completarse en cada PC antes de la demostración
- Guardar las IPs documentadas para referencia futura
- Verificar que los 3 PCs están en la misma red local (mismo rango de IPs)

**¡Éxito en la demostración!** 🎉
