# 🚀 GUÍA COMPLETA DE DESPLIEGUE

## 📋 Tabla de Contenidos

1. [Requisitos Previos](#1-requisitos-previos)
2. [Configuración de Red](#2-configuración-de-red)
3. [Construcción de Imágenes](#3-construcción-de-imágenes)
4. [Despliegue PC2 (Kafka + Central)](#4-despliegue-pc2-kafka--central)
5. [Despliegue PC3 (CPs)](#5-despliegue-pc3-cps)
6. [Despliegue PC1 (Driver)](#6-despliegue-pc1-driver)
7. [Verificación del Sistema](#7-verificación-del-sistema)
8. [Pruebas Básicas](#8-pruebas-básicas)
9. [Comandos Útiles](#9-comandos-útiles)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. REQUISITOS PREVIOS

### 1.1. Software Necesario

**En los 3 PCs:**
- ✅ Docker Desktop instalado y funcionando
- ✅ Git (para clonar el proyecto)
- ✅ Editor de texto (VSCode, Notepad++, etc.)

**Versiones mínimas:**
- Docker: 20.10+
- Docker Compose: 2.0+

### 1.2. Verificar Instalación

```powershell
# Verificar Docker
docker --version
docker-compose --version

# Verificar que Docker está funcionando
docker ps
```

**Resultado esperado:**
```
Docker version 24.0.x
Docker Compose version v2.x.x
CONTAINER ID   IMAGE   ...
(lista vacía está OK)
```

---

## 2. CONFIGURACIÓN DE RED

### 2.1. Obtener IPs de los PCs

**En cada PC, ejecutar:**

```powershell
ipconfig
```

**Buscar la dirección IPv4 de tu red local:**
```
Adaptador de LAN inalámbrica Wi-Fi:
   Dirección IPv4. . . . . . . . . : 192.168.1.XXX
```

**Anotar las IPs:**
- PC1 (Driver): `192.168.1.XXX`
- PC2 (Central/Kafka): `192.168.1.XXX`
- PC3 (CPs): `192.168.1.XXX`

---

### 2.2. Configurar Firewall

**En PC2 (Kafka/Central), ejecutar como Administrador:**

```powershell
# Abrir PowerShell como Administrador
# Permitir puertos de Kafka y Central
New-NetFirewallRule -DisplayName "Kafka Port" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Central Port" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow
```

**En PC3 (CPs), ejecutar como Administrador:**

```powershell
# Permitir puertos de Monitors
New-NetFirewallRule -DisplayName "Monitor Ports" -Direction Inbound -LocalPort 5500-5502 -Protocol TCP -Action Allow
```

---

### 2.3. Editar network_config.py

**En los 3 PCs, editar el archivo `SD/network_config.py`:**

```powershell
# Navegar al proyecto
cd C:\Users\TU_USUARIO\Desktop\SD\SD

# Editar con tu editor favorito
notepad network_config.py
# O
code network_config.py
```

**Cambiar estas líneas con las IPs reales:**

```python
# ============================================================================
# IPs DE LOS 3 PCs (CAMBIAR POR TUS IPs REALES)
# ============================================================================
PC1_IP = "192.168.1.XXX"  # ⚠️ IP de PC1 (Driver)
PC2_IP = "192.168.1.XXX"  # ⚠️ IP de PC2 (Kafka/Central)
PC3_IP = "192.168.1.XXX"  # ⚠️ IP de PC3 (CPs)

# Kafka Broker (siempre en PC2)
KAFKA_BROKER_IP = PC2_IP
KAFKA_BROKER = f"{KAFKA_BROKER_IP}:9092"
```

**Ejemplo con IPs reales:**
```python
PC1_IP = "192.168.1.100"  # Driver
PC2_IP = "192.168.1.235"  # Kafka/Central
PC3_IP = "192.168.1.150"  # CPs
```

**Guardar el archivo.**

---

## 3. CONSTRUCCIÓN DE IMÁGENES

### 3.1. PC2 - Construir Imágenes de Central

```powershell
# En PC2
cd C:\Users\TU_USUARIO\Desktop\SD\SD

# Construir imágenes
docker-compose -f docker-compose.pc2.yml build
```

**⏱️ Tiempo:** 5-10 minutos (primera vez)

**Resultado esperado:**
```
[+] Building 123.4s (15/15) FINISHED
Successfully built abc123def456
Successfully tagged ev-central:latest
```

---

### 3.2. PC3 - Construir Imágenes de CPs

```powershell
# En PC3
cd C:\Users\TU_USUARIO\Desktop\SD\SD

# Construir imágenes
docker-compose -f docker-compose.pc3.yml build
```

**⏱️ Tiempo:** 5-10 minutos (primera vez)

**Resultado esperado:**
```
Successfully built abc123def456
Successfully tagged ev-cp-engine:latest
Successfully tagged ev-cp-monitor:latest
```

---

### 3.3. PC1 - Construir Imagen de Driver

```powershell
# En PC1
cd C:\Users\TU_USUARIO\Desktop\SD\SD

# Construir imagen
docker-compose -f docker-compose.pc1.yml build
```

**⏱️ Tiempo:** 3-5 minutos (primera vez)

**Resultado esperado:**
```
Successfully built abc123def456
Successfully tagged ev-driver:latest
```

---

## 4. DESPLIEGUE PC2 (Kafka + Central)

### 4.1. Iniciar Servicios

```powershell
# En PC2
cd C:\Users\TU_USUARIO\Desktop\SD\SD

# Iniciar Kafka + Zookeeper + Central
docker-compose -f docker-compose.pc2.yml up -d
```

**⏱️ Tiempo:** 10-15 segundos

---

### 4.2. Verificar que están funcionando

```powershell
# Ver contenedores activos
docker ps
```

**Resultado esperado:**
```
CONTAINER ID   IMAGE              STATUS         PORTS                    NAMES
abc123def456   ev-central:latest  Up 10 seconds  0.0.0.0:8000->8000/tcp  ev-central
def456abc789   confluentinc/...   Up 15 seconds  0.0.0.0:9092->9092/tcp  kafka
ghi789jkl012   confluentinc/...   Up 20 seconds  2181/tcp                zookeeper
```

**✅ Deben aparecer 3 contenedores: `zookeeper`, `kafka`, `ev-central`**

---

### 4.3. Ver logs de Central

```powershell
# Ver logs en tiempo real
docker logs -f ev-central
```

**Resultado esperado:**
```
[KAFKA] 🔄 Attempt 1/15 to connect to Kafka at 192.168.1.235:9092
[KAFKA] ✅ Connected to Kafka successfully!
[KAFKA] 📡 Consumer started, listening to ['driver-events', 'cp-events']
[HTTP] Server started on http://0.0.0.0:8000
✅ All services started successfully!
```

**Si ves esto, PC2 está OK. Presiona `Ctrl+C` para salir de los logs.**

---

### 4.4. Abrir Dashboard Central (Opcional)

**En el navegador de PC2 (o cualquier PC en la red):**

```
http://192.168.1.235:8002
```
*(Cambiar por tu IP de PC2)*

**Deberías ver el dashboard administrativo de Central.**

---

## 5. DESPLIEGUE PC3 (CPs)

### 5.1. Iniciar Engines + Monitors

```powershell
# En PC3
cd C:\Users\TU_USUARIO\Desktop\SD\SD

# Iniciar 3 CPs (cada uno con Engine + Monitor)
docker-compose -f docker-compose.pc3.yml up -d
```

**⏱️ Tiempo:** 10-15 segundos

---

### 5.2. Verificar que están funcionando

```powershell
# Ver contenedores activos
docker ps
```

**Resultado esperado:**
```
CONTAINER ID   IMAGE                 STATUS         PORTS                    NAMES
abc123         ev-cp-engine:latest   Up 10 seconds  0.0.0.0:5100->5100/tcp  ev-cp-engine-001
def456         ev-cp-monitor:latest  Up 10 seconds  0.0.0.0:5500->5500/tcp  ev-cp-monitor-001
ghi789         ev-cp-engine:latest   Up 10 seconds  0.0.0.0:5101->5101/tcp  ev-cp-engine-002
jkl012         ev-cp-monitor:latest  Up 10 seconds  0.0.0.0:5501->5501/tcp  ev-cp-monitor-002
mno345         ev-cp-engine:latest   Up 10 seconds  0.0.0.0:5102->5102/tcp  ev-cp-engine-003
pqr678         ev-cp-monitor:latest  Up 10 seconds  0.0.0.0:5502->5502/tcp  ev-cp-monitor-003
```

**✅ Deben aparecer 6 contenedores: 3 engines + 3 monitors**

---

### 5.3. Ver logs de un Engine

```powershell
# Ver logs de CP_001
docker logs -f ev-cp-engine-001
```

**Resultado esperado:**
```
================================================================================
  ⚡ EV CHARGING POINT ENGINE - CP_001
================================================================================
  Location:       Parking Norte
  Max Power:      22.0 kW
  Tariff:         €0.30/kWh
  Health Port:    5100
================================================================================

[CP_001] ✅ Kafka initialized
[CP_001] ✅ Auto-registro enviado a Central
[CP_001] 🏥 Health check TCP server started on port 5100

🎮 INTERACTIVE CLI MENU - CP_001
Commands available:
  [P] Plug in    - Simulate vehicle connection
  [U] Unplug     - Simulate vehicle disconnection
  [F] Fault      - Simulate hardware failure
  [R] Recover    - Recover from failure
  [S] Status     - Show current CP status
  [Q] Quit       - Shutdown the CP
```

**Si ves esto, CP_001 está funcionando. Presiona `Ctrl+C` para salir.**

---

### 5.4. Ver logs de un Monitor

```powershell
# Ver logs de Monitor CP_001
docker logs -f ev-cp-monitor-001
```

**Resultado esperado:**
```
================================================================================
  🏥 EV MONITOR - Supervising CP_001
================================================================================
  Monitored CP:    CP_001
  Engine Host:     ev-cp-engine-001
  Engine Port:     5100
  Dashboard Port:  5500
================================================================================

[MONITOR-CP_001] ✅ Kafka initialized
[MONITOR-CP_001] 🔐 Authenticating with Central...
[MONITOR-CP_001] ✅ Monitor validated and ready to monitor CP_001
[MONITOR-CP_001] 🏥 Starting TCP health check loop (every 1 second)

[MONITOR-CP_001] ✅ Health check: Engine OK
[MONITOR-CP_001] ✅ Health check: Engine OK
[MONITOR-CP_001] ✅ Health check: Engine OK
```

**Si ves esto, Monitor está funcionando correctamente.**

---

### 5.5. Abrir Dashboards de Monitores (Opcional)

**En el navegador de cualquier PC en la red:**

```
http://192.168.1.150:5500  (Monitor CP_001)
http://192.168.1.150:5501  (Monitor CP_002)
http://192.168.1.150:5502  (Monitor CP_003)
```
*(Cambiar por tu IP de PC3)*

---

### 5.6. Verificar auto-registro en Central

**Volver a PC2, ver logs de Central:**

```powershell
# En PC2
docker logs ev-central --tail 50
```

**Deberías ver:**
```
[KAFKA] 📨 Received event: CP_REGISTRATION from topic: cp-events
[CENTRAL] 💾 CP registrado/actualizado (auto-registro): CP_001
[KAFKA] 📨 Received event: CP_REGISTRATION from topic: cp-events
[CENTRAL] 💾 CP registrado/actualizado (auto-registro): CP_002
[KAFKA] 📨 Received event: CP_REGISTRATION from topic: cp-events
[CENTRAL] 💾 CP registrado/actualizado (auto-registro): CP_003
[KAFKA] 📨 Received event: MONITOR_AUTH from topic: cp-events
[CENTRAL] ✅ Monitor MONITOR-CP_001 authenticated and validated
[KAFKA] 📨 Received event: MONITOR_AUTH from topic: cp-events
[CENTRAL] ✅ Monitor MONITOR-CP_002 authenticated and validated
[KAFKA] 📨 Received event: MONITOR_AUTH from topic: cp-events
[CENTRAL] ✅ Monitor MONITOR-CP_003 authenticated and validated
```

**✅ Si ves esto, los CPs se registraron correctamente en Central.**

---

## 6. DESPLIEGUE PC1 (Driver)

### 6.1. Iniciar Driver

```powershell
# En PC1
cd C:\Users\TU_USUARIO\Desktop\SD\SD

# Iniciar Driver
docker-compose -f docker-compose.pc1.yml up -d
```

**⏱️ Tiempo:** 5 segundos

---

### 6.2. Verificar que está funcionando

```powershell
# Ver contenedores activos
docker ps
```

**Resultado esperado:**
```
CONTAINER ID   IMAGE               STATUS         PORTS                    NAMES
abc123def456   ev-driver:latest    Up 5 seconds   0.0.0.0:8001->8001/tcp  ev-driver
```

**✅ Debe aparecer 1 contenedor: `ev-driver`**

---

### 6.3. Ver logs de Driver

```powershell
# Ver logs
docker logs -f ev-driver
```

**Resultado esperado:**
```
================================================================================
  🚗 EV DRIVER - Aplicación del Conductor
================================================================================
  WebSocket Port:  8001
  Kafka Broker:    192.168.1.235:9092
  Dashboard:       http://localhost:8001
================================================================================

[DRIVER] ✅ Kafka producer and consumer initialized
[KAFKA] 📡 Consumer started, listening to ['central-events', 'cp-events']
[HTTP] Server started on http://0.0.0.0:8001
✅ All services started successfully!
```

**Si ves esto, Driver está funcionando.**

---

### 6.4. Abrir Dashboard Driver

**En el navegador de PC1 (o cualquier PC en la red):**

```
http://192.168.1.100:8001
```
*(Cambiar por tu IP de PC1)*

**Deberías ver el dashboard del conductor con:**
- Login de usuario
- Lista de CPs disponibles (CP_001, CP_002, CP_003)

---

## 7. VERIFICACIÓN DEL SISTEMA

### 7.1. Checklist de Estado

**En PC2 (Central):**
```powershell
docker ps | Select-String "zookeeper\|kafka\|central"
```
**✅ Deben aparecer 3 contenedores activos**

**En PC3 (CPs):**
```powershell
docker ps | Select-String "ev-cp"
```
**✅ Deben aparecer 6 contenedores activos (3 engines + 3 monitors)**

**En PC1 (Driver):**
```powershell
docker ps | Select-String "ev-driver"
```
**✅ Debe aparecer 1 contenedor activo**

---

### 7.2. Verificar Comunicación

**En navegador, abrir Dashboard Central:**
```
http://192.168.1.235:8002
```

**En el dashboard, deberías ver:**
- ✅ **3 CPs registrados:**
  - CP_001 - Estado: 🟢 AVAILABLE
  - CP_002 - Estado: 🟢 AVAILABLE
  - CP_003 - Estado: 🟢 AVAILABLE
- ✅ **0 sesiones activas** (por ahora)

**Si ves los 3 CPs en verde, el sistema está funcionando correctamente.**

---

## 8. PRUEBAS BÁSICAS

### 8.1. Prueba 1: Solicitar una carga

**En PC1, abrir Dashboard Driver:**
```
http://192.168.1.100:8001
```

**Pasos:**
1. **Login:**
   - Usuario: `Juan`
   - Clic en "Login"
   - Resultado esperado: ✅ "Login exitoso"

2. **Solicitar carga:**
   - Seleccionar `CP_001` de la lista
   - Clic en "Solicitar carga"
   - Resultado esperado: ✅ "Carga autorizada en CP_001"

3. **Observar progreso:**
   - Barra de progreso animada
   - kWh incrementando cada segundo
   - Coste (€) incrementando

4. **Detener carga:**
   - Clic en "Detener carga"
   - Resultado esperado: 🎫 Ticket con total kWh y €

**✅ Si esto funciona, el flujo completo está operativo.**

---

### 8.2. Prueba 2: Observar en Dashboard Central

**Mientras la carga está en progreso, abrir Dashboard Central:**
```
http://192.168.1.235:8002
```

**Deberías ver:**
- ✅ CP_001 en estado 🟡 **CHARGING** (amarillo)
- ✅ Sesión activa de Juan con kWh y € en tiempo real
- ✅ Al detener la carga, CP_001 vuelve a 🟢 **AVAILABLE**

---

### 8.3. Prueba 3: Interactuar con CLI del Engine

**En PC3, acceder al CLI interactivo de CP_001:**

```powershell
docker attach ev-cp-engine-001
```

**Dentro del CLI, probar comandos:**

1. **Ver estado:**
   - Pulsar `S` + Enter
   - Resultado: Muestra estado actual del CP

2. **Simular fallo:**
   - Pulsar `F` + Enter
   - Resultado: 
     - Engine reporta "🚨 HARDWARE FAILURE"
     - Monitor detecta en 1 segundo
     - Central marca CP como "FAULT" (rojo)

3. **Recuperar:**
   - Pulsar `R` + Enter
   - Resultado:
     - Engine reporta "✅ RECOVERING"
     - Monitor detecta OK
     - Central marca CP como "AVAILABLE" (verde)

4. **Salir sin detener:**
   - Presionar `Ctrl+P`, luego `Ctrl+Q`
   - El contenedor sigue funcionando

**✅ Si esto funciona, el sistema de detección de fallos está operativo.**

---

### 8.4. Prueba 4: Procesamiento por Lotes

**En PC1, ejecutar procesamiento automático de 10 servicios:**

```powershell
# Acceder al contenedor
docker exec -it ev-driver bash

# Dentro del contenedor
python EV_Driver/procesar_archivos.py EV_Driver/servicios.txt Juan
```

**Resultado esperado:**
```
[1/10] Solicitando carga en CP_001...
✅ Carga autorizada
... (progreso)
🔌 Carga finalizada: 5.23 kWh, €1.57
⏳ Esperando 4 segundos...

[2/10] Solicitando carga en CP_002...
✅ Carga autorizada
... (progreso)
🔌 Carga finalizada: 4.87 kWh, €1.46
⏳ Esperando 4 segundos...

... (hasta 10/10)

✅ PROCESAMIENTO COMPLETADO: 10/10 servicios
```

**✅ Si esto funciona, el sistema puede procesar servicios autónomamente.**

---

## 9. COMANDOS ÚTILES

### 9.1. Ver logs de todos los servicios

```powershell
# PC2 - Central
docker-compose -f docker-compose.pc2.yml logs -f

# PC3 - CPs
docker-compose -f docker-compose.pc3.yml logs -f

# PC1 - Driver
docker-compose -f docker-compose.pc1.yml logs -f
```

---

### 9.2. Detener servicios

```powershell
# PC2 - Detener Central
docker-compose -f docker-compose.pc2.yml down

# PC3 - Detener CPs
docker-compose -f docker-compose.pc3.yml down

# PC1 - Detener Driver
docker-compose -f docker-compose.pc1.yml down
```

---

### 9.3. Reiniciar servicios

```powershell
# PC2 - Reiniciar Central
docker-compose -f docker-compose.pc2.yml restart

# PC3 - Reiniciar un CP específico
docker restart ev-cp-engine-001 ev-cp-monitor-001

# PC1 - Reiniciar Driver
docker-compose -f docker-compose.pc1.yml restart
```

---

### 9.4. Ver estado de contenedores

```powershell
# Ver todos los contenedores activos
docker ps

# Ver todos (incluyendo detenidos)
docker ps -a

# Ver solo nombres
docker ps --format "{{.Names}}"
```

---

### 9.5. Limpiar sistema

```powershell
# Detener y eliminar todos los contenedores
docker-compose -f docker-compose.pc2.yml down
docker-compose -f docker-compose.pc3.yml down
docker-compose -f docker-compose.pc1.yml down

# Eliminar redes huérfanas
docker network prune -f

# Eliminar volúmenes no usados (CUIDADO: borra base de datos)
docker volume prune -f
```

---

## 10. TROUBLESHOOTING

### 10.1. Error: "Cannot connect to Kafka"

**Síntoma:**
```
[KAFKA] ⚠️ Attempt 1/15 failed: [Errno 111] Connection refused
```

**Solución:**
1. Verificar que Kafka está funcionando en PC2:
   ```powershell
   docker ps | Select-String "kafka"
   ```

2. Verificar que el firewall permite puerto 9092:
   ```powershell
   Test-NetConnection -ComputerName 192.168.1.235 -Port 9092
   ```

3. Verificar IP en `network_config.py` es correcta

---

### 10.2. Error: "Port already in use"

**Síntoma:**
```
Error: bind: address already in use
```

**Solución:**
```powershell
# Ver qué proceso usa el puerto (ej: 8000)
netstat -ano | findstr :8000

# Detener contenedores que usen ese puerto
docker ps
docker stop <container_id>
```

---

### 10.3. CPs no aparecen en Dashboard Central

**Síntoma:** Dashboard Central muestra 0 CPs

**Solución:**
1. Verificar logs de Engine:
   ```powershell
   docker logs ev-cp-engine-001
   ```
   Buscar: `✅ Auto-registro enviado a Central`

2. Verificar logs de Central:
   ```powershell
   docker logs ev-central
   ```
   Buscar: `💾 CP registrado/actualizado: CP_001`

3. Si no aparece, reiniciar Engine:
   ```powershell
   docker restart ev-cp-engine-001
   ```

---

### 10.4. Monitor no detecta Engine

**Síntoma:** Monitor muestra "Engine Timeout"

**Solución:**
1. Verificar que Engine está funcionando:
   ```powershell
   docker ps | Select-String "engine-001"
   ```

2. Verificar puerto health check:
   ```powershell
   docker logs ev-cp-engine-001 | Select-String "Health check TCP server"
   ```
   Debe decir: `Health check TCP server started on port 5100`

3. Reiniciar Monitor:
   ```powershell
   docker restart ev-cp-monitor-001
   ```

---

### 10.5. Driver no puede solicitar carga

**Síntoma:** Dashboard Driver muestra "❌ Carga denegada"

**Causas comunes:**
1. **Usuario no existe:** Verificar base de datos
2. **Balance insuficiente:** Usuario necesita ≥ €5.00
3. **CP no disponible:** Verificar estado en Central
4. **Sesión activa previa:** Usuario ya tiene carga en progreso

**Solución:**
```powershell
# Ver logs de Central para ver la razón
docker logs ev-central --tail 50 | Select-String "AUTHORIZATION"
```

---

### 10.6. Dashboards no cargan

**Síntoma:** Navegador muestra "Cannot connect" o "ERR_CONNECTION_REFUSED"

**Solución:**
1. Verificar que el contenedor está funcionando:
   ```powershell
   docker ps | Select-String "central\|driver\|monitor"
   ```

2. Verificar puertos:
   ```powershell
   # Central: 8000
   # Driver: 8001
   # Monitors: 5500, 5501, 5502
   netstat -ano | findstr ":8000"
   ```

3. Verificar firewall:
   ```powershell
   # Permitir puerto temporalmente
   New-NetFirewallRule -DisplayName "Test Port" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```

4. Probar desde localhost primero:
   ```
   http://localhost:8002
   ```

---

## 11. RESUMEN RÁPIDO

### Para despliegue completo desde cero:

**1. Configurar IPs en `network_config.py` (3 PCs)**

**2. PC2 (Kafka + Central):**
```powershell
cd C:\Users\TU_USUARIO\Desktop\SD\SD
docker-compose -f docker-compose.pc2.yml build
docker-compose -f docker-compose.pc2.yml up -d
```

**3. PC3 (CPs):**
```powershell
cd C:\Users\TU_USUARIO\Desktop\SD\SD
docker-compose -f docker-compose.pc3.yml build
docker-compose -f docker-compose.pc3.yml up -d
```

**4. PC1 (Driver):**
```powershell
cd C:\Users\TU_USUARIO\Desktop\SD\SD
docker-compose -f docker-compose.pc1.yml build
docker-compose -f docker-compose.pc1.yml up -d
```

**5. Verificar:**
```
http://192.168.1.235:8002  (Central)
http://192.168.1.100:8001  (Driver)
http://192.168.1.150:5500  (Monitor CP_001)
```

**✅ SISTEMA DESPLEGADO Y FUNCIONANDO**

---

## 12. CONTACTO Y SOPORTE

**Si tienes problemas:**
1. Revisa la sección [Troubleshooting](#10-troubleshooting)
2. Verifica logs de cada contenedor
3. Asegúrate de que las IPs son correctas
4. Verifica que el firewall permite los puertos

**Logs completos para debugging:**
```powershell
docker-compose -f docker-compose.pc2.yml logs > logs_pc2.txt
docker-compose -f docker-compose.pc3.yml logs > logs_pc3.txt
docker-compose -f docker-compose.pc1.yml logs > logs_pc1.txt
```

---

**🎉 ¡Felicitaciones! Tu sistema EV Charging está desplegado y funcionando.**

