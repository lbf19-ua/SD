# 🚀 INSTRUCCIONES PARA TU DESPLIEGUE

## 📋 Tu Configuración

- **ESTE PC (192.168.1.235):** CENTRAL + Kafka
- **OTRO PC (192.168.1.228):** Driver + Monitor

---

## ✅ EN ESTE PC (192.168.1.235 - Central)

### Paso 1: Verificar Network Config

Ya está configurado:
```python
PC2_IP = "192.168.1.235"  # ← Tu IP
```

### Paso 2: Abrir Firewall (Como Admin)

```powershell
New-NetFirewallRule -DisplayName "Kafka Broker" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Kafka UI" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Central WS" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow
```

### Paso 3: Iniciar Docker

```powershell
cd C:\Users\luisb\Desktop\SD\SD
docker-compose -f docker-compose.pc2.yml up -d --build
```

**ESO ES TODO** - No necesitas compilar nada manualmente. Docker hace todo.

### Paso 4: Verificar

```powershell
docker-compose -f docker-compose.pc2.yml ps
```

Deberías ver:
```
NAME              STATUS
ev-kafka-broker   Up
ev-kafka-ui       Up
ev-central        Up
```

---

## ✅ EN EL OTRO PC (192.168.1.228 - Driver + Monitor)

### Paso 1: Editar Network Config

Edita `network_config.py` con los mismos valores:
```python
PC1_IP = "192.168.1.228"  # IP del OTRO PC
PC2_IP = "192.168.1.235"  # Tu IP
PC3_IP = "192.168.1.228"  # IP del OTRO PC
```

### Paso 2: Copiar Base de Datos

Copia `ev_charging.db` desde este PC (192.168.1.235) al otro PC.

**Opciones:**
- USB
- Compartir carpeta
- Red local

### Paso 3: Abrir Firewall

```powershell
New-NetFirewallRule -DisplayName "Driver WS" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Monitor WS" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
```

### Paso 4: Iniciar Docker

```powershell
cd SD

# Driver
docker-compose -f docker-compose.pc1.yml up -d --build

# Monitor
docker-compose -f docker-compose.pc3.yml up -d --build
```

**También se instala automáticamente** - No necesitas compilar.

---

## 🔍 VERIFICAR CONECTIVIDAD

En el OTRO PC (192.168.1.228):

```powershell
# Probar conexión con Central
ping 192.168.1.235

# Probar puerto Kafka
Test-NetConnection 192.168.1.235 -Port 9092
```

Ambos deben funcionar.

---

## ✅ URLs DE ACCESO

| Dashboard | URL |
|-----------|-----|
| **Kafka UI** | http://192.168.1.235:8080 |
| **Admin Dashboard** | http://192.168.1.235:8002 |
| **Driver Dashboard** | http://192.168.1.228:8001 |
| **Monitor Dashboard** | http://192.168.1.228:8003 |

---

## 📝 NOTA SOBRE "COMPILAR"

**NO necesitas compilar nada**. Docker automáticamente:

1. Copia `requirements.txt`
2. Ejecuta `pip install -r requirements.txt`
3. Instala todos los paquetes

**Todo esto sucede cuando ejecutas:**
```powershell
docker-compose up -d --build
```

El flag `--build` construye las imágenes, no es compilación manual.

---

## 🎯 RESUMEN

1. ✅ Editar IPs en `network_config.py` (ya hecho)
2. ✅ Abrir firewall
3. ✅ Iniciar Docker con `--build`
4. ✅ ¡Listo! Los paquetes se instalan automáticamente

**NO hay compilación manual necesaria.** 🎉

