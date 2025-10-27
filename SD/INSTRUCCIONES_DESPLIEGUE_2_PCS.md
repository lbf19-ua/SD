# 🚀 Instrucciones de Despliegue en 2 PCs

## 📋 Resumen de la Configuración Actual

### Este PC (PC2 - Central):
- **IP:** `192.168.1.235`
- **Rol:** Central + Kafka Broker
- **Interfaces:**
  - http://localhost:8002 → Dashboard Admin
  - http://localhost:8080 → Kafka UI
  - Puerto 5000 → Servidor Central
  - Puerto 9092 → Kafka Broker

### Otro PC (PC donde desplegar Driver + Monitor):
- **IP:** ⚠️ NECESITAS OBTENERLA (ejecutar `ipconfig` en ese PC)
- **Rol:** Driver + Monitor
- **Interfaces:**
  - http://localhost:8001 → Dashboard Driver
  - http://localhost:8003 → Dashboard Monitor

---

## 🔧 PASO 1: Configurar Red en el Otro PC

En el **otro PC**, edita el archivo `SD/network_config.py`:

```python
# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.235"  # ✅ IP del PC actual (PC2)

# PC1 - EV_Driver (Interfaz de conductor)  
PC1_IP = "YY.YY.YY.YY"  # ⚠️ CAMBIAR por la IP del otro PC

# PC3 - EV_CP (Monitor & Engine - Punto de carga)
PC3_IP = "YY.YY.YY.YY"  # ⚠️ Mismo IP que PC1 (mismo PC, diferentes puertos)
```

📝 **IMPORTANTE:** Usa la IP que aparezca cuando ejecutes `ipconfig` en el otro PC.

---

## 🚀 PASO 2: Desplegar Driver y Monitor en el Otro PC

En el **otro PC**, ejecuta:

```powershell
# Navegar al directorio
cd C:\Users\[TU_USUARIO]\Desktop\SD\SD

# Desplegar Driver
docker-compose -f docker-compose.pc1.yml up -d --build

# Desplegar Monitor
docker-compose -f docker-compose.pc3.yml up -d --build
```

---

## 🔥 PASO 3: Configurar Firewall en ESTE PC (PC2)

Para que el otro PC pueda conectarse a Kafka y Central, abre estos puertos:

```powershell
# Ejecutar como Administrador

# Puerto 9092 - Kafka
New-NetFirewallRule -DisplayName "Kafka Broker" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow

# Puerto 5000 - Central (ya debería estar abierto)
New-NetFirewallRule -DisplayName "Central Server" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow

# Puerto 8002 - Admin Dashboard
New-NetFirewallRule -DisplayName "Admin Dashboard" -Direction Inbound -LocalPort 8002 -Protocol TCP -Action Allow

# Puerto 8080 - Kafka UI (opcional, para ver mensajes)
New-NetFirewallRule -DisplayName "Kafka UI" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
```

---

## ✅ PASO 4: Verificar Conectividad

### En el otro PC, ejecuta:

```powershell
# Ping al PC2 (Central)
ping 192.168.1.235

# Verificar conexión a Kafka
telnet 192.168.1.235 9092
```

Si el ping funciona y telnet conecta, ¡estás listo!

---

## 🌐 Accesos a las Interfaces

### En ESTE PC (PC2 - Central):
- **Admin Dashboard:** http://localhost:8002
- **Kafka UI:** http://localhost:8080

### En el OTRO PC (Driver + Monitor):
- **Driver Dashboard:** http://localhost:8001
- **Monitor Dashboard:** http://localhost:8003

### Acceso remoto:
- **Admin Dashboard:** http://192.168.1.235:8002 (desde el otro PC)
- **Kafka UI:** http://192.168.1.235:8080 (desde el otro PC)

---

## 🧪 PASO 5: Prueba de Conexión

1. Abre el Dashboard Admin en este PC: http://localhost:8002
2. Abre el Dashboard Driver en el otro PC: http://localhost:8001
3. Registra un CP (Monitor en el otro PC)
4. Solicita un servicio desde el Driver (otro PC)
5. Verifica que los mensajes llegan a Central

---

## 📊 Visualizar Mensajes de Kafka

### En CUALQUIER PC de la red:
- **Kafka UI:** http://192.168.1.235:8080
- Ve a "Topics" → Verás 4 topics:
  - `driver-events` (mensajes del Driver)
  - `cp-events` (mensajes del Monitor)
  - `central-events` (respuestas de Central)
  - `monitor-events` (métricas del Monitor)

---

## 🐛 Solución de Problemas

### Error: "NoBrokersAvailable"
**Causa:** No puede conectarse a Kafka en PC2  
**Solución:**
1. Verifica firewall en PC2 (puerto 9092 abierto)
2. Verifica que `PC2_IP` en `network_config.py` es correcto
3. Verifica que Kafka está corriendo: `docker logs ev-kafka-broker`

### Error: "Connection refused"
**Causa:** Firewall bloqueando puerto  
**Solución:** Abre puertos con PowerShell (ver PASO 3)

### Dashboard no carga
**Causa:** Contenedores reiniciándose  
**Solución:** 
```powershell
docker logs ev-central
docker logs ev-driver
docker logs ev-monitor
```

---

## 📝 Checklist de Verificación

- [ ] IPs configuradas correctamente en `network_config.py` en ambos PCs
- [ ] Docker corriendo en ambos PCs
- [ ] Firewall configurado en PC2 (Central)
- [ ] Kafka UI accesible desde ambos PCs
- [ ] Admin Dashboard muestra estado de CPs
- [ ] Driver puede solicitar servicios
- [ ] Monitor recibe y procesa solicitudes

---

## 🎯 Siguientes Pasos

1. Registra algunos CPs desde el Monitor
2. Solicita servicios desde el Driver
3. Observa el flujo de mensajes en Kafka UI
4. Verifica que todo está sincronizado en el Admin Dashboard

¡Todo listo para el despliegue distribuido! 🎉

