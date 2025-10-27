# 🚀 Pasos Rápidos para Desplegar en el Otro PC

## 📝 PASO 1: Obtener la IP de este PC

Ejecuta en **PowerShell**:
```powershell
ipconfig
```

Busca "Dirección IPv4" y **CÓPIALA**. Ejemplo: `192.168.1.235`

---

## ⚙️ PASO 2: Configurar network_config.py

Edita el archivo `SD/network_config.py` en **el otro PC**:

```python
# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.235"  # ⚠️ PÉGALA AQUÍ la IP de arriba

# PC1 - EV_Driver (Interfaz de conductor)  
PC1_IP = "TU_IP_AQUI"  # ⚠️ IP del PC actual

# PC3 - EV_CP (Monitor & Engine - Punto de carga)
PC3_IP = "TU_IP_AQUI"  # ⚠️ Mismo que PC1
```

**IMPORTANTE:** También necesitas obtener **tu IP en el otro PC** con `ipconfig` y ponerla en `PC1_IP` y `PC3_IP`.

---

## 🐳 PASO 3: Desplegar Contenedores

Ejecuta en **PowerShell** desde `C:\Users\[TU_USUARIO]\Desktop\SD\SD`:

```powershell
# Desplegar Driver
docker-compose -f docker-compose.pc1.yml up -d --build

# Esperar 10 segundos
Start-Sleep -Seconds 10

# Desplegar Monitor  
docker-compose -f docker-compose.pc3.yml up -d --build
```

---

## ✅ PASO 4: Verificar Estado

```powershell
# Ver contenedores
docker ps

# Ver logs
docker logs ev-driver
docker logs ev-monitor
```

Si ves errores de "NoBrokersAvailable", **verifica el firewall en el PC de Central** (ejecuta el script `configurar_firewall.ps1` como Admin en el PC de Central).

---

## 🌐 Acceder a las Interfaces

- **Driver Dashboard:** http://localhost:8001
- **Monitor Dashboard:** http://localhost:8003
- **Admin Dashboard (Central):** http://192.168.1.235:8002
- **Kafka UI:** http://192.168.1.235:8080

---

## 🧪 Probar Conexión

1. Abre el **Monitor Dashboard** → Presiona "Registrar CP" para un punto de carga
2. Abre el **Admin Dashboard** → Deberías ver el CP aparecer
3. Abre el **Driver Dashboard** → Solicita un servicio
4. Verifica en **Kafka UI** que los mensajes están llegando

---

## 🐛 Problemas Comunes

### Error: "NoBrokersAvailable"
→ Ejecuta `configurar_firewall.ps1` como Admin en el PC de Central

### Contenedores reiniciándose
→ Verifica logs: `docker logs ev-driver` y `docker logs ev-monitor`

### No se ven los CPs en Admin Dashboard
→ Verifica que la IP en `network_config.py` es correcta

---

¡Listo! 🎉

