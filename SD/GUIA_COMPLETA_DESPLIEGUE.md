# 🚀 GUÍA COMPLETA DE DESPLIEGUE - Sistema EV Charging con Docker y Kafka

**Sistema de Gestión de Carga de Vehículos Eléctricos**  
**Despliegue Multi-PC con Docker, Kafka y WebSockets**

---

## 📋 TABLA DE CONTENIDOS

1. [Introducción](#introducción)
2. [Requisitos Previos](#requisitos-previos)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Preparación Inicial](#preparación-inicial)
5. [Configuración de Red](#configuración-de-red)
6. [Despliegue PC por PC](#despliegue-pc-por-pc)
7. [Verificación del Sistema](#verificación-del-sistema)
8. [Uso del Sistema](#uso-del-sistema)
9. [Comandos Útiles](#comandos-útiles)
10. [Troubleshooting](#troubleshooting)
11. [Mantenimiento](#mantenimiento)

---

## 📖 INTRODUCCIÓN

Este sistema permite la gestión de sesiones de carga de vehículos eléctricos distribuida en 3 ordenadores conectados en una red local:

- **PC1 (Driver)**: Interfaz para conductores que solicitan carga
- **PC2 (Central + Kafka)**: Servidor central que gestiona todo el sistema y el broker de mensajes Kafka
- **PC3 (Monitor)**: Dashboard de monitorización de puntos de carga

Todos los componentes se comunican a través de:
- **WebSockets**: Para interfaces web en tiempo real
- **TCP**: Para comunicación entre componentes de backend
- **Kafka**: Para mensajería asíncrona entre servicios

---

## 🔧 REQUISITOS PREVIOS

### Hardware y Red

#### En TODOS los PCs (PC1, PC2, PC3):
- ✅ Sistema operativo: **Windows 10/11** (o Linux/macOS con adaptaciones)
- ✅ RAM: Mínimo **4 GB** (recomendado 8 GB)
- ✅ Espacio en disco: Mínimo **5 GB** libres
- ✅ Conexión a la **misma red local** (LAN)
- ✅ Permisos de **administrador** (para configurar firewall)

### Software Requerido

#### 1. Docker Desktop
**TODOS LOS PCs deben tener Docker instalado**

**Descargar:**
- Windows/Mac: https://www.docker.com/products/docker-desktop
- Linux: `sudo apt install docker.io docker-compose` (Ubuntu/Debian)

**Verificar instalación:**
```powershell
docker --version
# Debe mostrar: Docker version 24.x.x o superior

docker-compose --version
# Debe mostrar: Docker Compose version 2.x.x o superior

docker ps
# Debe ejecutarse sin errores (lista contenedores corriendo)
```

**⚠️ IMPORTANTE**: Docker Desktop debe estar **ejecutándose** antes de continuar.

#### 2. Python 3.10 o superior
**SOLO en PC2** (para inicializar la base de datos)

**Descargar:** https://www.python.org/downloads/

**Verificar:**
```powershell
python --version
# Debe mostrar: Python 3.10.x o superior
```

#### 3. Git (Opcional)
Para clonar el repositorio

**Descargar:** https://git-scm.com/downloads

### Archivos del Sistema

Debes tener la carpeta `SD/` con todos estos archivos:

```
SD/
├── network_config.py              # Configuración de red
├── database.py                    # Gestión de base de datos
├── event_utils.py                 # Utilidades de Kafka
├── init_db.py                     # Inicializador de BD
├── requirements.txt               # Dependencias Python
│
├── EV_Central/
│   ├── EV_Central_WebSocket.py
│   ├── admin_dashboard.html
│   └── Dockerfile
│
├── EV_Driver/
│   ├── EV_Driver_WebSocket.py
│   ├── dashboard.html
│   └── Dockerfile
│
├── EV_CP_M/
│   ├── EV_CP_M_WebSocket.py
│   ├── monitor_dashboard.html
│   └── Dockerfile
│
├── docker-compose.pc1.yml         # Docker Compose para PC1
├── docker-compose.pc2.yml         # Docker Compose para PC2
├── docker-compose.pc3.yml         # Docker Compose para PC3
│
└── Scripts PowerShell:
    └── docker_manager.ps1         # Gestor Docker
```

---

## 🏗️ ARQUITECTURA DEL SISTEMA

```
┌────────────────────────────────────────────────────────────────────┐
│                      RED LOCAL (192.168.1.x)                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   ┌─────────────────┐        ┌─────────────────┐        ┌────────────────┐
│   │   PC1: DRIVER   │◄──────►│  PC2: CENTRAL   │◄──────►│  PC3: MONITOR  │
│   │                 │  TCP   │                 │  TCP   │                │
│   │  [Container]    │  WS    │  [Containers]   │  WS    │  [Container]   │
│   │  • EV_Driver    │ Kafka  │  • Kafka Broker │ Kafka  │  • EV_Monitor  │
│   │                 │        │  • Kafka UI     │        │                │
│   │  Puerto: 8001   │        │  • EV_Central   │        │  Puerto: 8003  │
│   └─────────────────┘        │                 │        └────────────────┘
│                              │  Puertos:       │
│                              │  - 9092 (Kafka) │
│                              │  - 8080 (UI)    │
│                              │  - 5000 (TCP)   │
│                              │  - 8002 (WS)    │
│                              └─────────────────┘
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Puertos Utilizados

| PC | Puerto | Servicio | Descripción |
|----|--------|----------|-------------|
| **PC1** | 8001 | HTTP/WS | Dashboard de Conductor |
| **PC2** | 5000 | TCP | Servidor Central |
| **PC2** | 8002 | HTTP/WS | Dashboard de Administración |
| **PC2** | 8080 | HTTP | Kafka UI (Monitorización) |
| **PC2** | 9092 | TCP | Kafka Broker |
| **PC3** | 8003 | HTTP/WS | Dashboard de Monitor |

### Topics de Kafka

El sistema utiliza estos topics para comunicación:
- `driver-events`: Eventos del conductor (inicio/fin de carga)
- `cp-events`: Eventos de puntos de carga (estado, alertas)
- `central-events`: Eventos del servidor central
- `monitor-events`: Eventos de monitorización

---

## 🎬 PREPARACIÓN INICIAL

### Paso 0: Obtener las IPs de tus PCs

**EN CADA PC**, abre PowerShell o Terminal y ejecuta:

**Windows:**
```powershell
ipconfig
```

**Linux/Mac:**
```bash
ifconfig
# o
ip addr show
```

**Busca la IP de tu red local**, ejemplo:
```
Adaptador de Ethernet:
   IPv4 Address. . . . . . : 192.168.1.50  ← Esta es tu IP
```

**Anota las 3 IPs:**
- PC1 IP: ________________
- PC2 IP: ________________
- PC3 IP: ________________

⚠️ **IMPORTANTE**: Las 3 IPs deben estar en la **misma red** (ej: todas 192.168.1.xxx)

---

## 🌐 CONFIGURACIÓN DE RED

### Obtener las IPs de los 3 PCs

En cada PC, abre terminal y ejecuta:

```powershell
ipconfig  # Windows
# o
ifconfig  # Linux/Mac
```

Busca la línea **"IPv4 Address"**:
```
   IPv4 Address. . . . . . : 192.168.1.50  ← Esta es tu IP
```

⚠️ **IMPORTANTE**: Las 3 IPs deben estar en la **misma red** (ej: todas 192.168.1.xxx)

### Editar network_config.py

Abre el archivo `network_config.py` y modifica estas 3 líneas con tus IPs reales:

```python
# ==== CONFIGURACIÓN DE IPS POR PC ====

PC1_IP = "192.168.1.10"  # ⚠️ CAMBIAR por la IP real del PC1 (Driver)
PC2_IP = "192.168.1.20"  # ⚠️ CAMBIAR por la IP real del PC2 (Central + Kafka)  
PC3_IP = "192.168.1.30"  # ⚠️ CAMBIAR por la IP real del PC3 (Monitor)
```

**Guarda el archivo.** ✅

---

```yaml
KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://broker:29092,PLAINTEXT_HOST://192.168.1.51:9092'
                                                                      ↑
                                                            Cambia a la IP real de PC2
```

---

## 🚀 DESPLIEGUE PC POR PC

### ⚠️ ORDEN IMPORTANTE

**DEBES seguir este orden:**
1. **PC2 PRIMERO** (Central + Kafka) - Es el núcleo del sistema
2. **PC1 y PC3 DESPUÉS** (pueden ser en paralelo)

---

### 🟦 PC2: CENTRAL + KAFKA (Iniciar PRIMERO)

**Este PC es el corazón del sistema. DEBE iniciarse primero.**

#### Paso 1: Inicializar Base de Datos

**Solo necesitas hacer esto UNA VEZ** (la primera vez):

```powershell
python init_db.py
```

Deberías ver:
```
Base de datos inicializada correctamente
Tablas creadas: users, charging_points, charging_sessions
```

Esto crea el archivo `ev_charging.db` en la carpeta `SD/`.

#### Paso 2: Construir e Iniciar Contenedores Docker

```powershell
docker-compose -f docker-compose.pc2.yml up -d --build
```

**Parámetros:**
- `-f docker-compose.pc2.yml`: Usar configuración de PC2
- `up`: Iniciar servicios
- `-d`: Modo detached (segundo plano)
- `--build`: Construir imágenes Docker

**Tiempo estimado:** 3-5 minutos la primera vez (descarga imágenes base)

#### Paso 4: Verificar que Todo Está Corriendo

```powershell
docker-compose -f docker-compose.pc2.yml ps
```

Deberías ver 3 contenedores en estado **Up**:
```
NAME              STATUS    PORTS
ev-kafka-broker   Up        0.0.0.0:9092->9092/tcp
ev-kafka-ui       Up        0.0.0.0:8080->8080/tcp
ev-central        Up        0.0.0.0:5000->5000/tcp, 0.0.0.0:8002->8002/tcp
```

#### Paso 3: Acceder a las Interfaces

Abre tu navegador y accede a:

**Kafka UI** (Monitorización de Kafka):
```
http://<IP_de_PC2>:8080
```
Ejemplo: `http://192.168.1.51:8080`

Deberías ver:
- Cluster: `ev-charging-cluster`
- Topics: `driver-events`, `cp-events`, `central-events`, `monitor-events`

**Admin Dashboard**:
```
http://<IP_de_PC2>:8002
```
Ejemplo: `http://192.168.1.51:8002`

#### Paso 4: Ver Logs (Opcional)

Para ver qué está pasando:

```powershell
# Ver logs de todos los servicios
docker-compose -f docker-compose.pc2.yml logs -f

# Ver solo logs de Kafka
docker-compose -f docker-compose.pc2.yml logs -f kafka-broker

# Ver solo logs de EV_Central
docker-compose -f docker-compose.pc2.yml logs -f ev-central
```

Presiona `Ctrl+C` para salir de los logs.

---

### 🟩 PC1: DRIVER

**⚠️ SOLO CONTINÚA SI PC2 YA ESTÁ CORRIENDO**

#### Paso 1: Copiar Base de Datos desde PC2

La base de datos se creó en PC2. Debes copiarla a PC1.

**Opción A: Por Red (Compartir Carpeta)**

En PC2:
1. Clic derecho en la carpeta `SD/`
2. Propiedades → Compartir
3. Compartir con red

En PC1:
1. Abre `\\<IP_PC2>\SD` en el explorador
2. Copia `ev_charging.db` a tu carpeta `SD/` local

**Opción B: USB**
1. Copia `ev_charging.db` a una USB desde PC2
2. Pégala en la carpeta `SD/` de PC1

#### Paso 2: Verificar Conectividad con PC2

```powershell
# Ping a PC2
ping <IP_PC2>

# Probar puerto Kafka (9092)
Test-NetConnection <IP_PC2> -Port 9092

# Probar puerto Central (5000)
Test-NetConnection <IP_PC2> -Port 5000
```

**Todos deben mostrar éxito.** Si alguno falla:
- Verifica que PC2 está corriendo
- Verifica que las IPs son correctas
- Ver sección de Troubleshooting para problemas de firewall

#### Paso 3: Iniciar Contenedor Docker

```powershell
docker-compose -f docker-compose.pc1.yml up -d --build
```

#### Paso 4: Verificar Estado

```powershell
docker-compose -f docker-compose.pc1.yml ps
```

Deberías ver:
```
NAME        STATUS    PORTS
ev-driver   Up        0.0.0.0:8001->8001/tcp
```

#### Paso 5: Acceder al Dashboard

Abre tu navegador:
```
http://<IP_PC1>:8001
```
Ejemplo: `http://192.168.1.50:8001`

Deberías ver el dashboard de conductor con opciones de login.

---

### 🟨 PC3: MONITOR

**⚠️ SOLO CONTINÚA SI PC2 YA ESTÁ CORRIENDO**

#### Paso 1: Copiar Base de Datos desde PC2

Igual que en PC1, copia `ev_charging.db` desde PC2 a la carpeta `SD/` de PC3.

#### Paso 2: Verificar Conectividad con PC2

```powershell
# Ping a PC2
ping <IP_PC2>

# Probar puerto Kafka (9092)
Test-NetConnection <IP_PC2> -Port 9092

# Probar puerto Central (5000)
Test-NetConnection <IP_PC2> -Port 5000
```

#### Paso 3: Iniciar Contenedor Docker

```powershell
docker-compose -f docker-compose.pc3.yml up -d --build
```

#### Paso 4: Verificar Estado

```powershell
docker-compose -f docker-compose.pc3.yml ps
```

Deberías ver:
```
NAME         STATUS    PORTS
ev-monitor   Up        0.0.0.0:8003->8003/tcp
```

#### Paso 5: Acceder al Dashboard

Abre tu navegador:
```
http://<IP_PC3>:8003
```
Ejemplo: `http://192.168.1.52:8003`

Deberías ver el dashboard de monitor con métricas de puntos de carga.

---

## ✅ VERIFICACIÓN DEL SISTEMA

### Checklist Post-Despliegue

Verifica que todos estos puntos estén OK:

#### ✅ PC2 (Central + Kafka)
- [ ] Contenedores corriendo: `docker-compose -f docker-compose.pc2.yml ps`
- [ ] Kafka UI accesible: `http://<PC2_IP>:8080`
- [ ] Admin Dashboard accesible: `http://<PC2_IP>:8002`
- [ ] 4 topics creados en Kafka UI

#### ✅ PC1 (Driver)
- [ ] Contenedor corriendo: `docker-compose -f docker-compose.pc1.yml ps`
- [ ] Dashboard accesible: `http://<PC1_IP>:8001`
- [ ] Puede hacer ping a PC2
- [ ] Puede conectar a puerto 9092 de PC2

#### ✅ PC3 (Monitor)
- [ ] Contenedor corriendo: `docker-compose -f docker-compose.pc3.yml ps`
- [ ] Dashboard accesible: `http://<PC3_IP>:8003`
- [ ] Puede hacer ping a PC2
- [ ] Puede conectar a puerto 9092 de PC2

### Verificar Topics de Kafka

En PC2:

```powershell
docker exec ev-kafka-broker kafka-topics.sh --bootstrap-server localhost:29092 --list
```

Deberías ver:
```
driver-events
cp-events
central-events
monitor-events
```

### Probar Flujo Completo

1. **En Driver Dashboard (PC1)**:
   - Login con usuario de prueba
   - Solicitar sesión de carga

2. **En Kafka UI (PC2)**:
   - Ir a Topics → `driver-events`
   - Ver mensajes en tiempo real

3. **En Admin Dashboard (PC2)**:
   - Ver la sesión activa en la tabla

4. **En Monitor Dashboard (PC3)**:
   - Ver métricas actualizadas
   - Ver estado de puntos de carga

---

## 💻 USO DEL SISTEMA

### Usuarios por Defecto

El sistema se inicializa con estos usuarios de prueba:

| Usuario | Contraseña | Rol | Servicios Preferidos |
|---------|-----------|-----|---------------------|
| `user1` | `pass1` | conductor | SERVICIO_B, SERVICIO_C |
| `user2` | `pass2` | conductor | SERVICIO_A |
| `user3` | `pass3` | conductor | SERVICIO_C |

### Flujo de Uso Típico

#### 1. Conductor Solicita Carga (PC1)

1. Accede a `http://<PC1_IP>:8001`
2. Login con `user1` / `pass1`
3. Selecciona punto de carga disponible
4. Inicia sesión de carga
5. Sistema publica evento a Kafka (`driver-events`)

#### 2. Central Procesa (PC2)

1. EV_Central consume evento de `driver-events`
2. Valida disponibilidad
3. Asigna punto de carga
4. Actualiza base de datos
5. Publica estado a `central-events`

#### 3. Monitor Visualiza (PC3)

1. EV_Monitor consume eventos de Kafka
2. Actualiza dashboard en tiempo real
3. Muestra métricas y alertas
4. Publica eventos de monitorización a `monitor-events`

### Ver Mensajes en Kafka UI

1. Accede a `http://<PC2_IP>:8080`
2. Click en un topic (ej: `driver-events`)
3. Click en "Messages"
4. Selecciona "Live Mode" para ver en tiempo real
5. Filtra por clave, valor, timestamp, etc.

---

## 🛠️ COMANDOS ÚTILES

### Gestión con docker_manager.ps1 (RECOMENDADO)

Este script simplifica la gestión:

```powershell
# Ver estado
.\docker_manager.ps1 status

# Iniciar servicios
.\docker_manager.ps1 up

# Iniciar + construir
.\docker_manager.ps1 up -Build

# Detener servicios
.\docker_manager.ps1 down

# Ver logs (últimas 50 líneas)
.\docker_manager.ps1 logs

# Ver logs en tiempo real
.\docker_manager.ps1 logs -Follow

# Solo construir imágenes
.\docker_manager.ps1 build

# Ver estado de todos los PCs
.\docker_manager.ps1 all
```

### Comandos Docker Directos

#### Gestión de Contenedores

```powershell
# Iniciar
docker-compose -f docker-compose.pcX.yml up -d

# Detener
docker-compose -f docker-compose.pcX.yml down

# Reiniciar un servicio
docker-compose -f docker-compose.pcX.yml restart <servicio>

# Reconstruir e iniciar
docker-compose -f docker-compose.pcX.yml up -d --build

# Ver estado
docker-compose -f docker-compose.pcX.yml ps

# Ver logs
docker-compose -f docker-compose.pcX.yml logs -f

# Ver logs de servicio específico
docker-compose -f docker-compose.pcX.yml logs -f <servicio>
```

#### Inspección

```powershell
# Ver todos los contenedores
docker ps

# Ver uso de recursos
docker stats

# Ver logs de un contenedor
docker logs <container_name>

# Ver logs en tiempo real
docker logs -f <container_name>

# Ejecutar comando en contenedor
docker exec -it <container_name> bash

# Ver información del contenedor
docker inspect <container_name>
```

#### Kafka (Solo PC2)

```powershell
# Listar topics
docker exec ev-kafka-broker kafka-topics.sh --bootstrap-server localhost:29092 --list

# Describir un topic
docker exec ev-kafka-broker kafka-topics.sh --bootstrap-server localhost:29092 --describe --topic driver-events

# Consumir mensajes (desde el principio)
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events --from-beginning

# Consumir mensajes (solo nuevos)
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events

# Ver grupos de consumidores
docker exec ev-kafka-broker kafka-consumer-groups.sh --bootstrap-server localhost:29092 --list

# Describir grupo de consumidor
docker exec ev-kafka-broker kafka-consumer-groups.sh --bootstrap-server localhost:29092 --describe --group <group_name>
```

#### Limpieza

```powershell
# Detener y borrar contenedores
docker-compose -f docker-compose.pcX.yml down

# Detener y borrar contenedores + volúmenes
docker-compose -f docker-compose.pcX.yml down -v

# Limpiar imágenes sin usar
docker image prune

# Limpiar todo (¡CUIDADO!)
docker system prune -a
```

---

## 🔥 TROUBLESHOOTING

### Problema 1: Docker no arranca

**Síntomas:**
- Error al ejecutar `docker ps`
- Mensaje: "Cannot connect to Docker daemon"

**Soluciones:**

1. **Verificar que Docker Desktop está corriendo:**
   - Windows: Buscar icono de Docker en la bandeja del sistema
   - Si no está: Abre Docker Desktop desde el menú inicio

2. **Reiniciar Docker Desktop:**
   - Clic derecho en icono → Quit Docker Desktop
   - Abrir de nuevo Docker Desktop

3. **Verificar instalación:**
   ```powershell
   docker --version
   docker-compose --version
   ```

---

### Problema 2: No puedo conectar a Kafka desde PC1/PC3

**Síntomas:**
- Contenedor se reinicia constantemente
- Logs muestran: "Connection refused" al puerto 9092
- `Test-NetConnection` falla

**Soluciones:**

1. **Verificar que PC2 está corriendo:**
   ```powershell
   # En PC2
   docker-compose -f docker-compose.pc2.yml ps
   ```
   Kafka debe estar "Up"

2. **Verificar firewall en PC2:**
   ```powershell
   # En PC2 como admin
   Get-NetFirewallRule -DisplayName "*Kafka*"
   ```
   Debe mostrar regla habilitada

3. **Re-abrir puerto si es necesario:**
   ```powershell
   # En PC2 como admin
   New-NetFirewallRule -DisplayName "Kafka Broker" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
   ```

4. **Verificar IP configurada:**
   - Abrir `docker-compose.pc2.yml`
   - Verificar línea `KAFKA_ADVERTISED_LISTENERS`
   - Debe tener la IP REAL de PC2

5. **Probar conectividad desde PC1/PC3:**
   ```powershell
   ping <IP_PC2>
   Test-NetConnection <IP_PC2> -Port 9092
   ```

---

### Problema 3: "Port already in use"

**Síntomas:**
- Error al iniciar: "port is already allocated"
- Docker compose falla

**Soluciones:**

1. **Verificar qué está usando el puerto:**
   ```powershell
   netstat -ano | findstr :8001
   # Cambia 8001 por el puerto que falla
   ```

2. **Identificar el proceso:**
   La última columna es el PID (Process ID)

3. **Ver qué proceso es:**
   ```powershell
   tasklist | findstr <PID>
   ```

4. **Detener el proceso:**
   ```powershell
   # Opción 1: Cerrar el programa manualmente
   
   # Opción 2: Matar el proceso (¡CUIDADO!)
   taskkill /PID <PID> /F
   ```

5. **Reintentar iniciar Docker:**
   ```powershell
   docker-compose -f docker-compose.pcX.yml up -d
   ```

---

### Problema 4: Contenedor se reinicia constantemente

**Síntomas:**
- `docker ps` muestra estado "Restarting"
- Servicio no accesible

**Soluciones:**

1. **Ver logs del error:**
   ```powershell
   docker-compose -f docker-compose.pcX.yml logs <servicio>
   ```

2. **Errores comunes y soluciones:**

   **"ModuleNotFoundError":**
   - Falta una dependencia Python
   - Solución: Rebuild la imagen
   ```powershell
   docker-compose -f docker-compose.pcX.yml build --no-cache
   docker-compose -f docker-compose.pcX.yml up -d
   ```

   **"Connection refused" a Kafka:**
   - Ver [Problema 2](#problema-2-no-puedo-conectar-a-kafka-desde-pc1pc3)

   **"database is locked":**
   - Varios contenedores accediendo a la BD simultáneamente
   - Solución: Detener todos, copiar BD de nuevo, reiniciar en orden
   ```powershell
   # Detener todos
   docker-compose -f docker-compose.pc1.yml down
   docker-compose -f docker-compose.pc2.yml down
   docker-compose -f docker-compose.pc3.yml down
   
   # Copiar ev_charging.db desde PC2 a PC1 y PC3
   
   # Iniciar en orden: PC2 → PC1 → PC3
   ```

3. **Iniciar sin -d para ver errores:**
   ```powershell
   docker-compose -f docker-compose.pcX.yml up
   ```
   Presiona `Ctrl+C` para detener

---

### Problema 5: Dashboard no carga / Muestra error

**Síntomas:**
- Navegador muestra "Cannot connect"
- Página en blanco
- Error 502/503

**Soluciones:**

1. **Verificar que contenedor está corriendo:**
   ```powershell
   docker-compose -f docker-compose.pcX.yml ps
   ```
   Estado debe ser "Up"

2. **Verificar logs:**
   ```powershell
   docker logs <container_name>
   ```

3. **Verificar firewall:**
   ```powershell
   # Windows
   Get-NetFirewallRule -DisplayName "EV*"
   ```

4. **Probar acceso local:**
   ```powershell
   # En el mismo PC donde corre el contenedor
   curl http://localhost:8001
   # Cambia el puerto según el servicio
   ```

5. **Limpiar caché del navegador:**
   - Presiona `Ctrl+Shift+Delete`
   - Selecciona "Caché" e "Imágenes"
   - Limpia y recarga

6. **Intentar desde otro navegador:**
   - Chrome, Firefox, Edge

---

### Problema 6: "Cannot build image"

**Síntomas:**
- `docker-compose build` falla
- Error durante la construcción de imagen

**Soluciones:**

1. **Ver el error completo:**
   ```powershell
   docker-compose -f docker-compose.pcX.yml build
   ```

2. **Limpiar caché de Docker:**
   ```powershell
   docker builder prune
   ```

3. **Rebuild sin caché:**
   ```powershell
   docker-compose -f docker-compose.pcX.yml build --no-cache
   ```

4. **Verificar espacio en disco:**
   ```powershell
   docker system df
   ```

5. **Limpiar espacio si es necesario:**
   ```powershell
   # Limpiar imágenes sin usar
   docker image prune -a
   
   # Limpiar todo (¡CUIDADO!)
   docker system prune -a
   ```

---

### Problema 7: IPs incorrectas / No encuentran servicios

**Síntomas:**
- PC1/PC3 no pueden conectar a PC2
- Logs muestran "Connection refused"

**Soluciones:**

1. **Verificar IPs configuradas:**
   ```powershell
   # Ver tu IP actual
   ipconfig
   
   # Ver IP configurada en network_config.py
   type network_config.py | findstr "PC._IP"
   ```

2. **Editar network_config.py si es necesario:**
   ```powershell
   # Abre el archivo y corrige las IPs manualmente
   notepad network_config.py
   ```

3. **Reiniciar servicios:**
   ```powershell
   # PC2
   docker-compose -f docker-compose.pc2.yml down
   docker-compose -f docker-compose.pc2.yml up -d --build
   
   # PC1 y PC3
   docker-compose -f docker-compose.pc1.yml down
   docker-compose -f docker-compose.pc1.yml up -d
   ```

---

### Problema 8: Base de datos no existe

**Síntomas:**
- Error: "no such table: users"
- Dashboard no funciona

**Soluciones:**

1. **En PC2, reinicializar BD:**
   ```powershell
   python init_db.py
   ```

2. **Verificar que se creó:**
   ```powershell
   dir ev_charging.db
   ```

3. **Copiar a PC1 y PC3:**
   - Por red compartida o USB

4. **Verificar permisos:**
   - El archivo debe ser accesible para Docker
   - No debe estar en una carpeta protegida

---

### Problema 9: Windows Firewall bloquea conexiones

**Síntomas:**
- `Test-NetConnection` falla
- Ping funciona pero conexión al puerto no
- Kafka/dashboards inaccesibles desde otros PCs

**Soluciones:**

**Opción 1: Desactivar temporalmente** (Para pruebas - MÁS FÁCIL):
```powershell
# PowerShell como Administrador
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False
```

**⚠️ Recuerda reactivarlo después:**
```powershell
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True
```

**Opción 2: Abrir puertos específicos** (Recomendado para producción):

```powershell
# PowerShell como Administrador

# En PC1:
New-NetFirewallRule -DisplayName "EV Driver WS" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow

# En PC2:
New-NetFirewallRule -DisplayName "EV Central TCP" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV Admin WS" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Kafka UI" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Kafka Broker" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow

# En PC3:
New-NetFirewallRule -DisplayName "EV Monitor WS" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
```

**Opción 3: Verificar reglas existentes:**
```powershell
# Ver todas las reglas relacionadas
Get-NetFirewallRule -DisplayName "*EV*" | Format-Table Name, DisplayName, Enabled, Direction

# Ver regla específica
Get-NetFirewallRule -DisplayName "Kafka Broker" | Format-List *
```

**Opción 4: Eliminar y recrear regla:**
```powershell
# Si una regla está mal configurada
Remove-NetFirewallRule -DisplayName "Kafka Broker"
New-NetFirewallRule -DisplayName "Kafka Broker" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
```

---

## 🔄 MANTENIMIENTO

### Actualizar el Sistema

Cuando hagas cambios en el código:

```powershell
# Detener servicios
.\docker_manager.ps1 down

# O directamente:
docker-compose -f docker-compose.pcX.yml down

# Reconstruir e iniciar
.\docker_manager.ps1 up -Build

# O directamente:
docker-compose -f docker-compose.pcX.yml up -d --build
```

### Reiniciar un Servicio Específico

```powershell
# Reiniciar sin rebuild
docker-compose -f docker-compose.pc2.yml restart ev-central

# Detener, rebuild e iniciar
docker-compose -f docker-compose.pc2.yml stop ev-central
docker-compose -f docker-compose.pc2.yml build ev-central
docker-compose -f docker-compose.pc2.yml up -d ev-central
```

### Ver Logs Históricos

```powershell
# Últimas 100 líneas
docker-compose -f docker-compose.pc2.yml logs --tail=100

# Últimas 100 líneas de un servicio
docker-compose -f docker-compose.pc2.yml logs --tail=100 kafka-broker

# Filtrar por texto
docker logs ev-central | findstr "ERROR"

# Exportar logs a archivo
docker logs ev-central > logs_central.txt
```

### Backup de la Base de Datos

```powershell
# En PC2, crear backup
copy ev_charging.db ev_charging_backup_$(Get-Date -Format "yyyyMMdd_HHmmss").db

# Restaurar desde backup
copy ev_charging_backup_20251021_143000.db ev_charging.db
```

### Limpiar Datos de Kafka

Si quieres empezar de cero (borra todos los mensajes):

```powershell
# En PC2, detener Kafka
docker-compose -f docker-compose.pc2.yml down

# Borrar volumen (¡CUIDADO! Borra todos los datos)
docker-compose -f docker-compose.pc2.yml down -v

# Iniciar de nuevo
docker-compose -f docker-compose.pc2.yml up -d
```

### Monitorear Recursos

```powershell
# Ver CPU y RAM en tiempo real
docker stats

# Ver solo un contenedor
docker stats ev-central

# Ver espacio en disco
docker system df

# Ver información detallada
docker system df -v
```

### Detener Todo el Sistema

En orden inverso al inicio:

```powershell
# PC3 (Monitor)
docker-compose -f docker-compose.pc3.yml down

# PC1 (Driver)
docker-compose -f docker-compose.pc1.yml down

# PC2 (Central + Kafka) - al final
docker-compose -f docker-compose.pc2.yml down
```

Para borrar también volúmenes (datos persistentes):

```powershell
# Solo en PC2 si quieres borrar datos de Kafka
docker-compose -f docker-compose.pc2.yml down -v
```

---

## 📊 ACCESOS RÁPIDOS

### URLs del Sistema

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Kafka UI** | http://\<PC2_IP\>:8080 | Sin login |
| **Admin Dashboard** | http://\<PC2_IP\>:8002 | Sin login (por ahora) |
| **Driver Dashboard** | http://\<PC1_IP\>:8001 | user1/pass1, user2/pass2, user3/pass3 |
| **Monitor Dashboard** | http://\<PC3_IP\>:8003 | Sin login |

### Scripts Útiles

| Script | Descripción |
|--------|-------------|
| `docker_manager.ps1` | Gestionar contenedores Docker |

---

## 📝 NOTAS FINALES

### Recomendaciones

1. **IPs Estáticas**: Configura IPs estáticas en tu router para evitar que cambien con DHCP
2. **Backups**: Haz backup regular de `ev_charging.db`
3. **Logs**: Revisa logs periódicamente para detectar problemas
4. **Monitorización**: Usa Kafka UI para ver el flujo de mensajes
5. **Docker Desktop**: Mantenlo actualizado

### Seguridad

⚠️ **IMPORTANTE**: Este sistema es para **desarrollo/demostración**. No usar en producción sin:
- Implementar autenticación robusta
- Cifrar comunicaciones (HTTPS/WSS)
- Asegurar Kafka con SASL/SSL
- Validar y sanitizar todas las entradas
- Implementar rate limiting
- Añadir logging de auditoría

### Limitaciones Conocidas

- Base de datos SQLite no es óptima para múltiples escrituras concurrentes
- Sin autenticación en Admin Dashboard y Monitor
- Sin persistencia de sesiones (se pierden al reiniciar)
- Sin balanceo de carga
- Sin alta disponibilidad (solo 1 broker de Kafka)

### Mejoras Futuras

- Migrar a PostgreSQL o MySQL
- Implementar OAuth2/JWT para autenticación
- Añadir más brokers de Kafka para HA
- Implementar Kubernetes para orquestación
- Añadir métricas con Prometheus/Grafana
- Implementar CI/CD pipeline

---

## ✅ CHECKLIST FINAL

Antes de considerar el despliegue completo:

### Pre-Despliegue
- [ ] Docker Desktop instalado en los 3 PCs
- [ ] IPs obtenidas de los 3 PCs
- [ ] Archivos del sistema copiados a los 3 PCs
- [ ] Python instalado en PC2

### Configuración
- [ ] `network_config.py` editado con IPs correctas

### Despliegue PC2
- [ ] Base de datos inicializada (`python init_db.py`)
- [ ] Contenedores de PC2 corriendo
- [ ] Kafka UI accesible
- [ ] Admin Dashboard accesible
- [ ] 4 topics creados en Kafka

### Despliegue PC1
- [ ] Base de datos copiada desde PC2
- [ ] Conectividad con PC2 verificada
- [ ] Contenedor de PC1 corriendo
- [ ] Driver Dashboard accesible

### Despliegue PC3
- [ ] Base de datos copiada desde PC2
- [ ] Conectividad con PC2 verificada
- [ ] Contenedor de PC3 corriendo
- [ ] Monitor Dashboard accesible

### Verificación Final
- [ ] Flujo completo de carga probado
- [ ] Mensajes visibles en Kafka UI
- [ ] Dashboards actualizándose en tiempo real
- [ ] Sin errores en logs

---

## 🆘 SOPORTE

Si encuentras problemas no cubiertos en esta guía:

1. **Revisar logs**: `docker-compose logs -f`
2. **Ver sección Troubleshooting** más arriba
3. **Verificar configuración**: IPs, firewall, conectividad
4. **Reiniciar servicios**: `docker-compose down` → `up -d`
5. **Rebuild limpio**: `build --no-cache`

---

## 📚 RECURSOS ADICIONALES

### Documentación Oficial
- **Docker**: https://docs.docker.com/
- **Apache Kafka**: https://kafka.apache.org/documentation/
- **WebSockets**: https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API

### Comandos Docker Cheat Sheet
- https://docs.docker.com/get-started/docker_cheatsheet.pdf

### Kafka Cheat Sheet
- https://kafka.apache.org/quickstart

---

**¡Sistema listo para usar! 🎉**

**Última actualización**: Octubre 2025  
**Versión**: 2.0 - Docker Multi-PC con Kafka
