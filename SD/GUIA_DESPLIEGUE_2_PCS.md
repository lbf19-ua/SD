# 🖥️ GUÍA: DESPLIEGUE EN 2 PCs

## 📋 Distribución de Componentes

**PC1 (ESTE PC):**
- ✅ CENTRAL (EV_Central)
- ✅ Kafka Broker
- ✅ Kafka UI

**PC2 (OTRO PC):**
- ✅ DRIVER (EV_Driver)
- ✅ MONITOR (EV_CP_M)

---

## 🎯 PASO 1: Obtener las IPs

### En ESTE PC (PC1):

```powershell
ipconfig
```

Busca la línea:
```
IPv4 Address. . . . . . : 192.168.1.XX
```

**Anota esta IP:** ________________

### En EL OTRO PC (PC2):

```powershell
ipconfig
```

Busca la línea:
```
IPv4 Address. . . . . . : 192.168.1.YY
```

**Anota esta IP:** ________________

⚠️ **IMPORTANTE:** Ambas IPs deben estar en la misma red (ej: ambas 192.168.1.xxx)

---

## 🔧 PASO 2: Configurar network_config.py

### En ESTE PC (PC1 - Central):

Edita `SD/network_config.py`:

```python
# PC1 - EV_Driver (Interfaz de conductor)
PC1_IP = "192.168.1.YY"  # ← IP del OTRO PC donde está Driver

# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.XX"  # ← IP de ESTE PC

# PC3 - EV_CP (Monitor & Engine - Punto de carga)
PC3_IP = "192.168.1.YY"  # ← IP del OTRO PC donde está Monitor
```

**Ejemplo:**
- ESTE PC: 192.168.1.50 (Central)
- OTRO PC: 192.168.1.51 (Driver + Monitor)

```python
PC1_IP = "192.168.1.51"  # Driver está en PC2
PC2_IP = "192.168.1.50"  # Central está en ESTE PC
PC3_IP = "192.168.1.51"  # Monitor está en PC2
```

### En EL OTRO PC (PC2 - Driver+Monitor):

Copias los mismos valores en `network_config.py`.

---

## 🔥 PASO 3: Configurar Firewall

### En ESTE PC (PC1 - Central):

Como Administrador:

```powershell
# Abrir puertos para Kafka y Central
New-NetFirewallRule -DisplayName "Kafka Broker" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Kafka UI" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Central TCP" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Central WS" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow
```

### En EL OTRO PC (PC2 - Driver+Monitor):

```powershell
# Abrir puertos para Driver y Monitor
New-NetFirewallRule -DisplayName "Driver WS" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Monitor WS" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
```

---

## 🚀 PASO 4: Desplegar

### ⭐ EN ESTE PC (PC1 - Central + Kafka):

**Navega a:**
```powershell
cd C:\Users\luisb\Desktop\SD\SD
```

**Inicializar BD (solo primera vez):**
```powershell
python init_db.py
```

**Iniciar Docker:**
```powershell
docker-compose -f docker-compose.pc2.yml up -d --build
```

**Verificar:**
```powershell
docker-compose -f docker-compose.pc2.yml ps
```

**Deberías ver:**
```
NAME              STATUS
ev-kafka-broker   Up
ev-kafka-ui       Up
ev-central        Up
```

---

### 📦 EN EL OTRO PC (PC2 - Driver + Monitor):

**Navega a:**
```powershell
cd C:\Users\luisb\Desktop\SD\SD
```

**Copiar BD desde PC1:**
- Copiar `ev_charging.db` desde PC1 a esta carpeta SD/

**Iniciar Docker:**
```powershell
# Driver
docker-compose -f docker-compose.pc1.yml up -d --build

# Monitor
docker-compose -f docker-compose.pc3.yml up -d --build
```

**Verificar:**
```powershell
docker ps
```

---

## ✅ PASO 5: Verificación

### URLs de Acceso:

| Dashboard | URL | PC |
|-----------|-----|-----|
| **Kafka UI** | http://192.168.1.XX:8080 | PC1 |
| **Admin Dashboard** | http://192.168.1.XX:8002 | PC1 |
| **Driver Dashboard** | http://192.168.1.YY:8001 | PC2 |
| **Monitor Dashboard** | http://192.168.1.YY:8003 | PC2 |

**Reemplaza XX e YY con tus IPs reales.**

### Ver Logs:

**En PC1 (Central):**
```powershell
docker logs ev-central -f
```

**En PC2 (Driver/Monitor):**
```powershell
docker logs ev-driver -f
docker logs ev-monitor -f
```

---

## 🧪 PASO 6: Probar el Sistema

### En Driver Dashboard (PC2):

1. Acceder a http://192.168.1.YY:8001
2. Login: `driver1` / `pass123`
3. Solicitar carga
4. Observar logs en ambos PCs

### Verificar en Kafka UI (PC1):

1. Acceder a http://192.168.1.XX:8080
2. Topics → `driver-events`
3. Ver mensajes en tiempo real

---

## 🛠️ TROUBLESHOOTING

### ❌ Error: No conecta a Kafka

**Verificar firewall en PC1:**
```powershell
Get-NetFirewallRule -DisplayName "*Kafka*"
```

**Verificar IP de PC2 en network_config.py:**
```python
PC2_IP = "192.168.1.XX"  # Debe ser la IP REAL de PC1
```

**Probar conectividad desde PC2:**
```powershell
ping 192.168.1.XX
Test-NetConnection 192.168.1.XX -Port 9092
```

### ❌ Error: Puerto ocupado

```powershell
# Ver qué usa el puerto
netstat -ano | findstr :8001

# Matar proceso
taskkill /PID <PID> /F
```

---

## 📊 ORDEN DE INICIO

```
1. PC1 (Central + Kafka)  ← ESTE PC
2. PC2 (Driver + Monitor)  ← OTRO PC
```

**Mínimo 30 segundos entre ellos** para que Kafka esté listo.

---

## ✅ CHECKLIST

**PC1 (Este PC):**
- [ ] IP obtenida
- [ ] network_config.py editado
- [ ] Firewall configurado
- [ ] BD inicializada
- [ ] Docker corriendo
- [ ] Kafka UI accesible

**PC2 (Otro PC):**
- [ ] IP obtenida
- [ ] network_config.py editado
- [ ] Firewall configurado
- [ ] BD copiada desde PC1
- [ ] Docker corriendo (Driver)
- [ ] Docker corriendo (Monitor)

---

**¡Listo! Ya tienes el sistema desplegado en 2 PCs.** 🎉

