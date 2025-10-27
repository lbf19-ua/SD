# 📋 Instrucciones Simples para el Otro PC

## 🎯 Tu PC (Central) - LISTO
- IP: `192.168.1.235`
- Kafka: `192.168.1.235:9092`
- Dashboard: http://192.168.1.235:8002
- Estado: ✅ Corriendo

---

## 🖥️ En el OTRO PC

### 1️⃣ Editar `SD/network_config.py`

```python
# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.235"  # ✅ Esta es la IP de TU PC Central

# PC1 - EV_Driver (Interfaz de conductor)
PC1_IP = "TU_IP_DEL_OTRO_PC"  # ⚠️ Obtener con: ipconfig

# PC3 - EV_CP (Monitor & Engine - Punto de carga)
PC3_IP = "TU_IP_DEL_OTRO_PC"  # ⚠️ Mismo que PC1_IP
```

Guarda el archivo.

### 2️⃣ Desplegar contenedores

```powershell
cd C:\Users\[TU_USUARIO]\Desktop\SD\SD

# Desplegar Driver
docker-compose -f docker-compose.pc1.yml up -d --build

# Esperar 10 segundos
Start-Sleep -Seconds 10

# Desplegar Monitor  
docker-compose -f docker-compose.pc3.yml up -d --build
```

### 3️⃣ Verificar

```powershell
docker ps

# Deberías ver:
# ev-driver (Up)
# ev-monitor (Up)
```

### 4️⃣ Acceder a las interfaces

- **Driver**: http://localhost:8001
- **Monitor**: http://localhost:8003
- **Admin (remoto)**: http://192.168.1.235:8002
- **Kafka UI (remoto)**: http://192.168.1.235:8080

---

## ✅ Eso es TODO

**Si no conecta, verifica:**
- Que ambos PCs estén en la misma red (mismo Wi‑Fi)
- Que la IP en network_config.py sea correcta
- Que el firewall no bloquee el puerto 9092

---

**Configuración de Kafka**: Ya corregí el `PLACEHOLDER_PC2_IP` por `192.168.1.235` en el docker-compose de PC2.

