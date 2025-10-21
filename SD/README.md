# ⚡ Sistema de Gestión de Carga de Vehículos Eléctricos

Sistema distribuido multi-PC con Docker, Kafka y WebSockets para gestión de puntos de carga de vehículos eléctricos.

---

## 🚀 INICIO RÁPIDO

**LEE ESTO PRIMERO:** 👉 **[LEEME_PRIMERO.md](LEEME_PRIMERO.md)**

**GUÍA COMPLETA:** 👉 **[GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)**

### 🧪 Quiero probarlo en local primero

**Guía de prueba:** 👉 **[PRUEBA_LOCAL.md](PRUEBA_LOCAL.md)** 👈

```powershell
.\test_local.ps1  # Script automático que configura TODO
```

### Despliegue rápido (en cada PC):

```powershell
# 1. Editar network_config.py con tus IPs

# 2. Iniciar Docker
.\docker_manager.ps1 up -Build
```

---

## 📋 ARQUITECTURA

```
┌──────────────────────────────────────────────────────┐
│              RED LOCAL (192.168.1.x)                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────┐      ┌──────────┐      ┌──────────┐  │
│  │   PC1   │◄────►│   PC2    │◄────►│   PC3    │  │
│  │ Driver  │ TCP  │ Central  │ TCP  │ Monitor  │  │
│  │   WS    │ WS   │ + Kafka  │ WS   │    WS    │  │
│  │         │Kafka │          │Kafka │          │  │
│  │ :8001   │      │ :5000    │      │ :8003    │  │
│  └─────────┘      │ :8002    │      └──────────┘  │
│                   │ :8080    │                     │
│                   │ :9092    │                     │
│                   └──────────┘                     │
└──────────────────────────────────────────────────────┘
```

### Componentes por PC

- **PC1 (Driver)**: Interfaz para conductores → Puerto 8001
- **PC2 (Central + Kafka)**: Servidor central + Message broker → Puertos 5000, 8002, 8080, 9092
- **PC3 (Monitor)**: Dashboard de monitorización → Puerto 8003

---

## 🛠️ TECNOLOGÍAS

- **Docker & Docker Compose**: Contenerización y orquestación
- **Apache Kafka**: Message broker para comunicación asíncrona
- **WebSockets**: Comunicación en tiempo real para dashboards
- **Python 3.11**: Backend con asyncio
- **SQLite**: Base de datos persistente
- **HTML/CSS/JavaScript**: Frontend responsive

---

## 📦 REQUISITOS PREVIOS

### En TODOS los PCs:
- ✅ **Docker Desktop** (https://www.docker.com/products/docker-desktop)
- ✅ Windows 10/11, macOS o Linux
- ✅ 4 GB RAM mínimo
- ✅ Conexión a la misma red local

### Solo en PC2:
- ✅ **Python 3.10+** (https://www.python.org/downloads/)

---

## 📂 ESTRUCTURA DEL PROYECTO

```
SD/
├── EV_Central/              # Servidor central
│   ├── EV_Central_WebSocket.py
│   ├── admin_dashboard.html
│   └── Dockerfile
│
├── EV_Driver/               # Interfaz de conductor
│   ├── EV_Driver_WebSocket.py
│   ├── dashboard.html
│   └── Dockerfile
│
├── EV_CP_M/                 # Monitor de CPs
│   ├── EV_CP_M_WebSocket.py
│   ├── monitor_dashboard.html
│   └── Dockerfile
│
├── docker-compose.pc1.yml   # Config para PC1
├── docker-compose.pc2.yml   # Config para PC2
├── docker-compose.pc3.yml   # Config para PC3
│
├── network_config.py        # Config de red
├── database.py              # Gestión BD
├── event_utils.py           # Utilidades Kafka
├── init_db.py               # Inicializador BD
│
└── Scripts:
    ├── configure_network.ps1
    ├── docker_manager.ps1
    └── open_firewall_ports.ps1
```

---

## 🔧 CONFIGURACIÓN

**Guía rápida**: 👉 **[CONFIGURACION_RED.md](CONFIGURACION_RED.md)** 👈

### Resumen rápido:

1. **Obtener IPs** con `ipconfig` en cada PC
2. **Editar `network_config.py`** con las 3 IPs
3. **Iniciar Docker** en cada PC

Ver [CONFIGURACION_RED.md](CONFIGURACION_RED.md) para instrucciones paso a paso.

---

## 🚀 DESPLIEGUE

### Orden de despliegue: PC2 → PC1 → PC3

#### PC2 (PRIMERO):
```powershell
# Abrir firewall (como admin)
.\open_firewall_ports.ps1

# Inicializar BD (solo primera vez)
python init_db.py

# Iniciar Docker
docker-compose -f docker-compose.pc2.yml up -d --build
```

#### PC1:
```powershell
# Copiar ev_charging.db desde PC2

# Iniciar Docker
docker-compose -f docker-compose.pc1.yml up -d --build
```

#### PC3:
```powershell
# Copiar ev_charging.db desde PC2

# Iniciar Docker
docker-compose -f docker-compose.pc3.yml up -d --build
```

---

## 🌐 ACCESO AL SISTEMA

| Servicio | URL | Descripción |
|----------|-----|-------------|
| **Kafka UI** | http://\<PC2_IP\>:8080 | Monitorización de Kafka |
| **Admin Dashboard** | http://\<PC2_IP\>:8002 | Panel de administración |
| **Driver Dashboard** | http://\<PC1_IP\>:8001 | Interfaz de conductor |
| **Monitor Dashboard** | http://\<PC3_IP\>:8003 | Monitorización de CPs |

### Usuarios de prueba

| Usuario | Contraseña | Balance |
|---------|-----------|---------|
| user1 | pass1 | €150.00 |
| user2 | pass2 | €200.00 |
| user3 | pass3 | €75.50 |

---

## 🛠️ GESTIÓN DEL SISTEMA

### Con docker_manager.ps1 (recomendado):
```powershell
.\docker_manager.ps1 status       # Ver estado
.\docker_manager.ps1 up           # Iniciar
.\docker_manager.ps1 down         # Detener
.\docker_manager.ps1 logs -Follow # Ver logs
```

### Con docker-compose:
```powershell
docker-compose -f docker-compose.pcX.yml ps       # Estado
docker-compose -f docker-compose.pcX.yml logs -f  # Logs
docker-compose -f docker-compose.pcX.yml down     # Detener
```

---

## 📊 KAFKA

### Ver topics:
```powershell
docker exec ev-kafka-broker kafka-topics.sh --bootstrap-server localhost:29092 --list
```

### Ver mensajes:
```powershell
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events --from-beginning
```

---

## 🐛 TROUBLESHOOTING

### Docker no arranca
```powershell
docker --version
docker ps
# Reinicia Docker Desktop
```

### No conecta a Kafka
```powershell
# PC2: Verificar Kafka
docker-compose -f docker-compose.pc2.yml ps

# PC1/PC3: Probar conectividad
Test-NetConnection <PC2_IP> -Port 9092
```

### Puerto ocupado
```powershell
netstat -ano | findstr :8001
taskkill /PID <PID> /F
```

### 🔥 Firewall bloquea conexiones
Si tienes problemas de conectividad entre PCs:

```powershell
# Opción 1: Desactivar temporalmente Windows Firewall
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False

# Opción 2: Abrir puertos específicos (como Admin)
New-NetFirewallRule -DisplayName "EV Charging - PC1" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV Charging - PC2" -Direction Inbound -LocalPort 5000,8002,8080,9092 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "EV Charging - PC3" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
```

**Más soluciones:** Ver [GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)

---

## 📚 DOCUMENTACIÓN

- **[LEEME_PRIMERO.md](LEEME_PRIMERO.md)** - Inicio rápido
- **[GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)** - Guía completa y definitiva

---

## 🔄 FLUJO DE USO

1. **Conductor (PC1)** solicita carga → Publica a Kafka
2. **Central (PC2)** procesa solicitud → Asigna CP → Actualiza BD
3. **Monitor (PC3)** consume eventos → Actualiza dashboard
4. **WebSockets** actualizan todas las interfaces en tiempo real

---

## ✅ CARACTERÍSTICAS

- ✅ Arquitectura distribuida multi-PC
- ✅ Comunicación asíncrona con Kafka
- ✅ WebSockets para tiempo real
- ✅ Dashboards responsive
- ✅ Base de datos persistente
- ✅ Contenerización con Docker
- ✅ Healthchecks automáticos
- ✅ Auto-restart configurado
- ✅ Monitorización con Kafka UI

---

## 📝 LICENCIA

Este proyecto es para fines educativos.

---

## 🆘 SOPORTE

1. Ver [GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)
2. Revisar logs: `docker-compose logs -f`
3. Verificar conectividad: `Test-NetConnection`

---

**Desarrollado para Sistemas Distribuidos 2025**

**¡Disfruta tu sistema de carga de vehículos eléctricos! ⚡🚗**
