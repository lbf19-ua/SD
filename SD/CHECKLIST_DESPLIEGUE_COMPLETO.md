# ✅ CHECKLIST COMPLETO DE DESPLIEGUE

## 🔍 VERIFICACIÓN SISTEMÁTICA

---

## 1. 📦 INSTALACIÓN AUTOMÁTICA DE PAQUETES

### ✅ 1.1 Dockerfiles Configurados

| Componente | Dockerfile | Instala requirements.txt? |
|------------|------------|--------------------------|
| **EV_Central** | `EV_Central/Dockerfile` | ✅ SÍ (líneas 25-26) |
| **EV_Driver** | `EV_Driver/Dockerfile` | ✅ SÍ (líneas 24-25) |
| **EV_CP_M** | `EV_CP_M/Dockerfile` | ✅ SÍ (líneas 24-25) |

**Código en cada Dockerfile:**
```dockerfile
# Copiar requirements primero (para aprovechar cache de Docker)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
```

### ✅ 1.2 Contexto de Build

Todos los `docker-compose.yml` usan el contexto correcto:

```yaml
build:
  context: .          # ← Directorio raíz SD/
  dockerfile: EV_Central/Dockerfile
```

**Verificado:**
- ✅ `docker-compose.pc1.yml` - Línea 32-33
- ✅ `docker-compose.pc2.yml` - Línea 86-87
- ✅ `docker-compose.pc3.yml` - Línea 32-33

### 📋 1.3 Paquetes que se Instalan

Al ejecutar `docker-compose build`, se instalan automáticamente:

```
kafka-python==2.0.2
websockets==12.0
aiohttp==3.9.1
aiosignal==1.3.1
frozenlist==1.4.0
multidict==6.0.4
yarl==1.9.2
attrs==23.1.0
async-timeout==4.0.3
colorama==0.4.6
```

---

## 2. 🏗️ CONFIGURACIÓN DE DESPLIEGUE

### ✅ 2.1 Archivos docker-compose

| Archivo | Componente | Estado |
|---------|------------|--------|
| `docker-compose.pc1.yml` | EV_Driver | ✅ Configurado |
| `docker-compose.pc2.yml` | EV_Central + Kafka | ✅ Configurado |
| `docker-compose.pc3.yml` | EV_CP_M | ✅ Configurado |
| `docker-compose.local.yml` | Todos (local) | ✅ Configurado |

### ✅ 2.2 Volúmenes Montados

**PC1 (Driver):**
```yaml
volumes:
  - ./ev_charging.db:/app/data/ev_charging.db
  - ./network_config.py:/app/network_config.py
  - ./database.py:/app/database.py
  - ./event_utils.py:/app/event_utils.py
```

**PC2 (Central):**
```yaml
volumes:
  - ./ev_charging.db:/app/ev_charging.db
  - ./network_config.py:/app/network_config.py
  - ./database.py:/app/database.py
  - ./event_utils.py:/app/event_utils.py
```

**PC3 (Monitor):**
```yaml
volumes:
  - ./ev_charging.db:/app/data/ev_charging.db
  - ./network_config.py:/app/network_config.py
  - ./database.py:/app/database.py
  - ./event_utils.py:/app/event_utils.py
```

### ✅ 2.3 Variables de Entorno

**PC2 (Central + Kafka):**
```yaml
environment:
  - KAFKA_BROKER=broker:29092
  - PYTHONUNBUFFERED=1
```

**PC1 (Driver):**
```yaml
environment:
  - WS_PORT=8001
  - PYTHONUNBUFFERED=1
```

**PC3 (Monitor):**
```yaml
environment:
  - WS_PORT=8003
  - PYTHONUNBUFFERED=1
```

### ✅ 2.4 Puertos Expuestos

| Componente | Puerto | Protocolo |
|------------|--------|-----------|
| Kafka Broker | 9092 | TCP |
| Kafka UI | 8080 | HTTP |
| EV_Central TCP | 5000 | TCP |
| EV_Central WS | 8002 | WebSocket |
| EV_Driver WS | 8001 | WebSocket |
| EV_CP_M WS | 8003 | WebSocket |

### ⚠️ 2.5 Network Mode

- **PC2:** `ev-network` (bridge network)
- **PC1:** `host` (para conectar a PC2)
- **PC3:** `host` (para conectar a PC2)

**Razón:** PC1 y PC3 usan `network_mode: host` para que puedan conectarse directamente a los servicios en PC2 (Kafka broker).

---

## 3. 🚀 ORDEN DE DESPLIEGUE

### ✅ 3.1 Secuencia Obligatoria

```
1. PC2 (Central + Kafka)  ← PRIMERO (núcleo del sistema)
2. PC1 (Driver)            ← SEGUNDO (puede ir en paralelo con PC3)
3. PC3 (Monitor)           ← SEGUNDO (puede ir en paralelo con PC1)
```

### 📝 3.2 Comandos por PC

**PC2 - Paso 1:**
```powershell
cd SD

# Inicializar BD (solo primera vez)
python init_db.py

# Iniciar Docker
docker-compose -f docker-compose.pc2.yml up -d --build

# Verificar
docker-compose -f docker-compose.pc2.yml ps
```

**PC1 - Paso 2:**
```powershell
cd SD

# Copiar BD desde PC2 (si aplica)

# Iniciar Docker
docker-compose -f docker-compose.pc1.yml up -d --build

# Verificar
docker-compose -f docker-compose.pc1.yml ps
```

**PC3 - Paso 2 (en paralelo con PC1):**
```powershell
cd SD

# Copiar BD desde PC2 (si aplica)

# Iniciar Docker
docker-compose -f docker-compose.pc3.yml up -d --build

# Verificar
docker-compose -f docker-compose.pc3.yml ps
```

---

## 4. 🧪 VERIFICACIÓN POST-DESPLIEGUE

### ✅ 4.1 Contenedores Corriendo

**PC2 debe tener:**
```bash
NAME                 STATUS
ev-kafka-broker      Up
ev-kafka-ui          Up
ev-central           Up
```

**PC1 debe tener:**
```bash
NAME           STATUS
ev-driver      Up
```

**PC3 debe tener:**
```bash
NAME           STATUS
ev-monitor     Up
```

### ✅ 4.2 URLs de Acceso

| Servicio | URL | Estado Esperado |
|----------|-----|-----------------|
| Kafka UI | http://PC2_IP:8080 | Interface accesible |
| Admin Dashboard | http://PC2_IP:8002 | Dashboard funcional |
| Driver Dashboard | http://PC1_IP:8001 | Dashboard funcional |
| Monitor Dashboard | http://PC3_IP:8003 | Dashboard funcional |

### ✅ 4.3 Verificar Kafka Topics

En PC2:
```powershell
docker exec ev-kafka-broker kafka-topics.sh --bootstrap-server localhost:29092 --list
```

**Deberías ver:**
```
driver-events
cp-events
central-events
monitor-events
```

### ✅ 4.4 Verificar Logs

```powershell
# PC2
docker-compose -f docker-compose.pc2.yml logs -f

# PC1
docker-compose -f docker-compose.pc1.yml logs -f

# PC3
docker-compose -f docker-compose.pc3.yml logs -f
```

**Buscar:**
- ✅ `[KAFKA] Producer initialized`
- ✅ `[KAFKA] Consumer started`
- ✅ `WebSocket server started on port XXXX`
- ❌ NO debería haber: `ERROR`, `Connection refused`

---

## 5. 🔧 TROUBLESHOOTING RÁPIDO

### ❌ Problema: "requirements.txt not found"

**Causa:** Ejecutaste docker-compose desde subdirectorio.

**Solución:**
```powershell
# Verifica que estás en el directorio correcto
cd C:\Users\luisb\Desktop\SD\SD

# Lista archivos
dir

# Deberías ver: requirements.txt, docker-compose.pcX.yml, etc.
```

### ❌ Problema: "Cannot connect to Docker daemon"

**Solución:**
```powershell
# 1. Verificar que Docker Desktop está corriendo
docker --version

# 2. Iniciar Docker Desktop manualmente si es necesario
```

### ❌ Problema: "Port already in use"

**Solución:**
```powershell
# Ver qué usa el puerto
netstat -ano | findstr :8001

# Detener proceso
taskkill /PID <PID> /F
```

### ❌ Problema: "Cannot connect to Kafka"

**Verificar:**
```powershell
# Desde PC1 o PC3
ping <PC2_IP>
Test-NetConnection <PC2_IP> -Port 9092

# Verificar firewall en PC2
Get-NetFirewallRule -DisplayName "*Kafka*"
```

---

## 6. ✅ CHECKLIST FINAL

Antes de considerar el despliegue completo:

### Pre-Despliegue
- [ ] Docker Desktop instalado en los 3 PCs
- [ ] IPs obtenidas y configuradas en `network_config.py`
- [ ] Base de datos inicializada en PC2 (`python init_db.py`)
- [ ] Firewall configurado o deshabilitado temporalmente

### Despliegue
- [ ] PC2 iniciado y Kafka corriendo
- [ ] PC2 ev-central corriendo
- [ ] PC1 iniciado
- [ ] PC3 iniciado

### Verificación
- [ ] Kafka UI accesible
- [ ] Admin Dashboard accesible
- [ ] Driver Dashboard accesible
- [ ] Monitor Dashboard accesible
- [ ] Sin errores en logs

### Funcionalidad
- [ ] Login en Driver funciona
- [ ] Solicitud de carga funciona
- [ ] Estado se actualiza en Admin
- [ ] Estado se actualiza en Monitor
- [ ] Eventos visibles en Kafka UI

---

## 🎯 CONCLUSIÓN

✅ **INSTALACIÓN AUTOMÁTICA DE PAQUETES:** ✅ CUMPLE
- requirements.txt se copia automáticamente
- pip install se ejecuta durante el build
- No requiere instalación manual

✅ **DESPLIEGUE CORRECTO:** ✅ CUMPLE
- Archivos docker-compose configurados
- Orden de despliegue documentado
- Volúmenes y puertos correctos

✅ **MULTIPLES INSTANCIAS:** ✅ CUMPLE
- Múltiples Drivers posibles
- Múltiples CPs posibles
- Inicio/parada dinámica
- Crash simulation posible

**El sistema está LISTO para despliegue en corrección.** 🎉

