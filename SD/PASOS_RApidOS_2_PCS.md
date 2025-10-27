# ⚡ PASOS RÁPIDOS - Despliegue en 2 PCs

## 🎯 SITUACIÓN ACTUAL

- **TU IP (Este PC):** 192.168.1.235 ← Este PC ejecuta CENTRAL
- **OTRO PC:** Necesitas su IP ← Ese PC ejecuta DRIVER + MONITOR

---

## 📝 PASO 1: Obtener IP del Otro PC

En el OTRO PC, ejecuta:
```powershell
ipconfig
```

Busca: `IPv4 Address. . . . . . : 192.168.1.XX`

Anota esa IP: ________________

---

## ⚙️ PASO 2: Editar Configuración

### En ESTE PC (192.168.1.235):

Edita `SD/network_config.py` y cambia:

```python
# PC1 - EV_Driver (Interfaz de conductor)
PC1_IP = "192.168.1.XX"  # ← IP del OTRO PC

# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.235"  # ← Tu IP actual

# PC3 - EV_CP (Monitor & Engine - Punto de carga)
PC3_IP = "192.168.1.XX"  # ← IP del OTRO PC
```

### En EL OTRO PC:

Copias la misma configuración.

---

## 🚀 PASO 3: Desplegar

### En ESTE PC (192.168.1.235):

```powershell
cd SD
python init_db.py
docker-compose -f docker-compose.pc2.yml up -d --build
```

### En EL OTRO PC:

```powershell
cd SD
# Copiar ev_charging.db desde este PC
docker-compose -f docker-compose.pc1.yml up -d --build
docker-compose -f docker-compose.pc3.yml up -d --build
```

---

## ✅ PASO 4: Verificar

### URLs de Acceso:

```
Kafka UI:        http://192.168.1.235:8080
Admin Dashboard: http://192.168.1.235:8002
Driver:          http://192.168.1.XX:8001
Monitor:          http://192.168.1.XX:8003
```

### Ver Logs:

```powershell
# En este PC
docker logs ev-central -f

# En el otro PC
docker logs ev-driver -f
docker logs ev-monitor -f
```

---

## ⚡ Listo!

Sistema desplegado en 2 PCs. 🎉

