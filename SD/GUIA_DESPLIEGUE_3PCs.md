# 🚀 Guía de Despliegue - Sistema EV Charging en 3 PCs

## 📋 Índice
1. [Requisitos Previos](#requisitos-previos)
2. [Despliegue en PC2 (Central + Kafka)](#pc2-central--kafka)
3. [Despliegue en PC3 (Charging Points)](#pc3-charging-points)
4. [Despliegue en PC1 (Driver)](#pc1-driver)
5. [Verificación del Sistema](#verificación-del-sistema)
6. [Troubleshooting](#troubleshooting)

---

## ✅ Requisitos Previos

### En TODOS los PCs:
1. **Docker y Docker Compose instalados**
   ```bash
   # Verificar instalación
   docker --version
   docker-compose --version
   ```

2. **Python 3.8+** (para scripts auxiliares)
   ```bash
   python --version
   ```

3. **Git** (para clonar el repositorio)
   ```bash
   git --version
   ```

4. **Firewall configurado** (permite comunicación entre PCs)

5. **Todos los PCs en la misma red local**

---

## 🖥️ PC2 - Central + Kafka (DESPLIEGUE PRIMERO)

### Paso 1: Obtener IP de PC2

**Windows:**
```powershell
ipconfig | findstr IPv4
# Ejemplo: 192.168.1.100
```

**Linux/Mac:**
```bash
hostname -I
# Ejemplo: 192.168.1.100
```

**⚠️ IMPORTANTE:** Anota esta IP, la necesitarás en PC1 y PC3.

### Paso 2: Clonar/Copiar el Repositorio

```bash
# Si usas Git
git clone <tu-repositorio>
cd SD/SD

# O copiar los archivos directamente
```

### Paso 3: Configurar network_config.py

Editar `network_config.py`:
```python
# Cambiar PC2_IP por la IP real obtenida en Paso 1
PC2_IP = "192.168.1.100"  # ⚠️ CAMBIAR POR TU IP REAL
```

### Paso 4: Crear archivo .env

Crear archivo `.env` en la raíz del proyecto:
```bash
# En Windows (PowerShell)
New-Item -Path .env -ItemType File

# En Linux/Mac
touch .env
```

**Contenido del .env:**
```env
# IP real de este ordenador (PC2)
PC2_IP=192.168.1.100

# Kafka Broker (usado internamente por contenedores Docker)
KAFKA_BROKER=broker:29092

# Puerto de Kafka
KAFKA_PORT=9092
```

**⚠️ IMPORTANTE:** Reemplazar `192.168.1.100` por la IP real de PC2.

### Paso 5: Configurar Firewall (Windows - PowerShell como Admin)

```powershell
# Kafka Broker
New-NetFirewallRule -DisplayName "EV Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow

# EV Central Dashboard
New-NetFirewallRule -DisplayName "EV Central" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow

# Kafka UI (opcional)
New-NetFirewallRule -DisplayName "Kafka UI" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
```

### Paso 6: Inicializar Base de Datos

```bash
# Si tienes script de inicialización
python reset_db_correcto.py

# O crear manualmente si es necesario
```

### Paso 7: Iniciar Servicios

```bash
# Iniciar todos los servicios
docker-compose -f docker-compose.pc2.yml up -d

# Ver logs en tiempo real
docker-compose -f docker-compose.pc2.yml logs -f

# Ver logs de un servicio específico
docker-compose -f docker-compose.pc2.yml logs -f ev-central
docker-compose -f docker-compose.pc2.yml logs -f kafka-broker
```

### Paso 8: Verificar que PC2 funciona

1. **Verificar contenedores:**
   ```bash
   docker ps
   # Deberías ver: ev-kafka-broker, ev-central, ev-kafka-ui
   ```

2. **Acceder a dashboards:**
   - **Admin Dashboard:** http://localhost:8002
   - **Kafka UI:** http://localhost:8080

3. **Verificar conectividad:**
   ```bash
   # Desde otro PC en la red, probar:
   telnet 192.168.1.100 9092  # Kafka
   telnet 192.168.1.100 8002  # Central
   ```

**✅ PC2 está listo cuando:**
- Todos los contenedores están corriendo
- Puedes acceder al Admin Dashboard
- Kafka está accesible desde la red (puerto 9092 abierto)

---

## 🔋 PC3 - Charging Points (DESPLIEGUE SEGUNDO)

### Paso 1: Obtener IP de PC2

**Desde PC3, verificar conectividad con PC2:**
```bash
# Windows
ping 192.168.1.100  # IP de PC2
Test-NetConnection 192.168.1.100 -Port 9092

# Linux/Mac
ping 192.168.1.100
nc -zv 192.168.1.100 9092
```

### Paso 2: Clonar/Copiar el Repositorio

```bash
# Mismo proceso que en PC2
git clone <tu-repositorio>
cd SD/SD
```

### Paso 3: Configurar network_config.py

Editar `network_config.py`:
```python
# Cambiar PC2_IP por la IP real de PC2
PC2_IP = "192.168.1.100"  # ⚠️ IP REAL DE PC2
```

### Paso 4: Crear archivo .env

Crear archivo `.env` en la raíz del proyecto:
```bash
# Windows (PowerShell)
New-Item -Path .env -ItemType File

# Linux/Mac
touch .env
```

**Contenido del .env:**
```env
# IP real de PC2 (donde está Kafka)
PC2_IP=192.168.1.100

# Kafka Broker (IP real de PC2:puerto)
KAFKA_BROKER=192.168.1.100:9092

# Puerto de Kafka
KAFKA_PORT=9092
```

**⚠️ CRÍTICO:** `KAFKA_BROKER` debe ser `IP_PC2:9092`, NO `broker:29092` (eso solo funciona en PC2 dentro de Docker).

### Paso 5: Copiar Base de Datos

Copiar `ev_charging.db` desde PC2 a PC3:
```bash
# Opción 1: Usar SCP (Linux/Mac)
scp usuario@192.168.1.100:/ruta/a/SD/SD/ev_charging.db .

# Opción 2: Compartir carpeta/red
# Copiar manualmente desde PC2 a PC3
```

**⚠️ IMPORTANTE:** PC3 necesita la misma BD que PC2 para funcionar correctamente.

### Paso 6: Configurar Firewall (Windows - PowerShell como Admin)

```powershell
# Health Check Ports (Engines)
New-NetFirewallRule -DisplayName "EV Engines" -Direction Inbound -LocalPort 5100-5103 -Protocol TCP -Action Allow

# Monitor Dashboards
New-NetFirewallRule -DisplayName "EV Monitors" -Direction Inbound -LocalPort 5500-5503 -Protocol TCP -Action Allow
```

### Paso 7: Iniciar Servicios

```bash
# Iniciar todos los servicios (3 Engines + 3 Monitors)
docker-compose -f docker-compose.pc3.yml up -d

# Ver logs en tiempo real
docker-compose -f docker-compose.pc3.yml logs -f

# Ver logs de un servicio específico
docker-compose -f docker-compose.pc3.yml logs -f ev-cp-engine-001
docker-compose -f docker-compose.pc3.yml logs -f ev-cp-monitor-001
```

### Paso 8: Verificar que PC3 funciona

1. **Verificar contenedores:**
   ```bash
   docker ps
   # Deberías ver: ev-cp-engine-001/002/003, ev-cp-monitor-001/002/003
   ```

2. **Acceder a dashboards de Monitores:**
   - **Monitor CP_001:** http://localhost:5500
   - **Monitor CP_002:** http://localhost:5501
   - **Monitor CP_003:** http://localhost:5502

3. **Verificar conectividad con PC2:**
   ```bash
   # Desde PC3, probar conexión a Kafka en PC2
   telnet 192.168.1.100 9092
   ```

**✅ PC3 está listo cuando:**
- Todos los contenedores están corriendo
- Los Engines se auto-registran en Central (ver logs)
- Los Monitores se autentican con Central (ver logs)
- Puedes acceder a los dashboards de Monitor

---

## 🚗 PC1 - Driver (DESPLIEGUE ÚLTIMO)

### Paso 1: Obtener IP de PC2

**Desde PC1, verificar conectividad con PC2:**
```bash
# Windows
ping 192.168.1.100  # IP de PC2
Test-NetConnection 192.168.1.100 -Port 9092

# Linux/Mac
ping 192.168.1.100
nc -zv 192.168.1.100 9092
```

### Paso 2: Clonar/Copiar el Repositorio

```bash
# Mismo proceso que en PC2 y PC3
git clone <tu-repositorio>
cd SD/SD
```

### Paso 3: Configurar network_config.py

Editar `network_config.py`:
```python
# Cambiar PC2_IP por la IP real de PC2
PC2_IP = "192.168.1.100"  # ⚠️ IP REAL DE PC2
```

### Paso 4: Crear archivo .env

Crear archivo `.env` en la raíz del proyecto:
```bash
# Windows (PowerShell)
New-Item -Path .env -ItemType File

# Linux/Mac
touch .env
```

**Contenido del .env:**
```env
# IP real de PC2 (donde está Kafka y Central)
PC2_IP=192.168.1.100

# Kafka Broker (IP real de PC2:puerto)
KAFKA_BROKER=192.168.1.100:9092

# Puerto de Kafka
KAFKA_PORT=9092
```

**⚠️ CRÍTICO:** `KAFKA_BROKER` debe ser `IP_PC2:9092`, NO `broker:29092`.

### Paso 5: Copiar Base de Datos

Copiar `ev_charging.db` desde PC2 a PC1:
```bash
# Mismo proceso que en PC3
```

### Paso 6: Configurar Firewall (Windows - PowerShell como Admin)

```powershell
# Driver Dashboard
New-NetFirewallRule -DisplayName "EV Driver" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
```

### Paso 7: Iniciar Servicios

```bash
# Iniciar Driver
docker-compose -f docker-compose.pc1.yml up -d

# Ver logs en tiempo real
docker-compose -f docker-compose.pc1.yml logs -f

# Ver logs del Driver
docker-compose -f docker-compose.pc1.yml logs -f ev-driver
```

### Paso 8: Verificar que PC1 funciona

1. **Verificar contenedores:**
   ```bash
   docker ps
   # Deberías ver: ev-driver
   ```

2. **Acceder a Driver Dashboard:**
   - **Driver Dashboard:** http://localhost:8001

3. **Verificar conectividad con PC2:**
   ```bash
   telnet 192.168.1.100 9092  # Kafka
   ```

**✅ PC1 está listo cuando:**
- El contenedor está corriendo
- Puedes acceder al Driver Dashboard
- Puedes hacer login y ver puntos de carga

---

## ✅ Verificación del Sistema

### Checklist de Verificación

#### PC2 (Central + Kafka):
- [ ] Contenedores corriendo: `ev-kafka-broker`, `ev-central`, `ev-kafka-ui`
- [ ] Admin Dashboard accesible: http://localhost:8002
- [ ] Kafka UI accesible: http://localhost:8080
- [ ] Kafka accesible desde red: puerto 9092 abierto

#### PC3 (Charging Points):
- [ ] Contenedores corriendo: 3 Engines + 3 Monitores
- [ ] Engines auto-registrados en Central (ver logs)
- [ ] Monitores autenticados con Central (ver logs)
- [ ] Dashboards de Monitor accesibles: http://localhost:5500/5501/5502
- [ ] Health checks funcionando (Monitores detectan Engines)

#### PC1 (Driver):
- [ ] Contenedor corriendo: `ev-driver`
- [ ] Driver Dashboard accesible: http://localhost:8001
- [ ] Puedes hacer login
- [ ] Puedes ver puntos de carga disponibles

### Prueba de Funcionamiento Completo

1. **Desde PC1 (Driver):**
   - Login como usuario
   - Solicitar autorización de carga
   - Verificar que se asigna un CP

2. **Desde PC2 (Admin):**
   - Verificar que aparece sesión activa
   - Verificar que el CP cambia a estado "charging"

3. **Desde PC3 (Monitor):**
   - Verificar que Monitor muestra carga activa
   - Verificar que Engine responde a health checks

4. **Verificar en Kafka UI (PC2):**
   - Ver mensajes en topics: `driver-events`, `cp-events`, `central-events`
   - Verificar que hay actividad en todos los topics

---

## 🔧 Troubleshooting

### Problema: PC3/PC1 no pueden conectar a Kafka en PC2

**Síntomas:**
- Errores de conexión en logs
- "Connection refused" o "Timeout"

**Solución:**
1. Verificar que PC2 está corriendo:
   ```bash
   # En PC2
   docker ps
   ```

2. Verificar firewall en PC2:
   ```powershell
   # Windows - PowerShell como Admin
   Get-NetFirewallRule -DisplayName "EV Kafka"
   ```

3. Verificar que `.env` en PC3/PC1 tiene:
   ```env
   KAFKA_BROKER=192.168.1.100:9092  # ⚠️ IP REAL DE PC2
   ```

4. Probar conectividad desde PC3/PC1:
   ```bash
   telnet 192.168.1.100 9092
   ```

### Problema: Engines no se auto-registran

**Síntomas:**
- No aparecen en Admin Dashboard
- Errores en logs de Engine

**Solución:**
1. Verificar logs del Engine:
   ```bash
   docker-compose -f docker-compose.pc3.yml logs ev-cp-engine-001
   ```

2. Verificar que `KAFKA_BROKER` en `.env` es correcto (IP_PC2:9092)

3. Verificar que Kafka está accesible desde PC3

### Problema: Monitores no detectan Engines

**Síntomas:**
- Health checks fallan en Monitor
- "Connection timeout" en logs

**Solución:**
1. Verificar que Engine está corriendo:
   ```bash
   docker ps | grep engine
   ```

2. Verificar puertos en firewall (PC3):
   ```powershell
   Get-NetFirewallRule -DisplayName "EV Engines"
   ```

3. Verificar logs del Monitor:
   ```bash
   docker-compose -f docker-compose.pc3.yml logs ev-cp-monitor-001
   ```

### Problema: Base de datos no sincronizada

**Síntomas:**
- Errores de "CP not found"
- Usuarios no encontrados

**Solución:**
1. Copiar `ev_charging.db` desde PC2 a PC1 y PC3
2. Reiniciar contenedores después de copiar BD

### Comandos Útiles

```bash
# Ver logs de todos los servicios
docker-compose -f docker-compose.pc2.yml logs -f
docker-compose -f docker-compose.pc3.yml logs -f
docker-compose -f docker-compose.pc1.yml logs -f

# Reiniciar un servicio específico
docker-compose -f docker-compose.pc2.yml restart ev-central

# Detener todos los servicios
docker-compose -f docker-compose.pc2.yml down
docker-compose -f docker-compose.pc3.yml down
docker-compose -f docker-compose.pc1.yml down

# Ver estado de contenedores
docker ps -a

# Limpiar todo (CUIDADO - elimina contenedores y volúmenes)
docker-compose -f docker-compose.pc2.yml down -v
```

---

## 📞 Orden de Despliegue

**⚠️ CRÍTICO:** Desplegar en este orden:

1. **PRIMERO:** PC2 (Central + Kafka)
2. **SEGUNDO:** PC3 (Charging Points)
3. **ÚLTIMO:** PC1 (Driver)

**Razón:** PC3 y PC1 necesitan Kafka y Central corriendo en PC2 antes de iniciar.

---

## ✅ Checklist Final

Antes de dar por terminado el despliegue, verifica:

- [ ] PC2: Central y Kafka corriendo
- [ ] PC3: Engines y Monitores corriendo
- [ ] PC1: Driver corriendo
- [ ] Todos los `.env` configurados con IP real de PC2
- [ ] Base de datos copiada en PC1 y PC3
- [ ] Firewalls configurados en todos los PCs
- [ ] Dashboards accesibles
- [ ] Prueba de carga completa funciona

**🎉 Sistema desplegado correctamente cuando todo el checklist está marcado!**

