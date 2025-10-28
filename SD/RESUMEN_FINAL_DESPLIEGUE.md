# 🎯 RESUMEN FINAL - Despliegue Multi-PC

## ✅ Estado Actual

### PC2 (Central - Este PC) - 172.20.10.8
- ✅ Kafka Broker corriendo: `172.20.10.8:9092`
- ✅ Central corriendo: `172.20.10.8:8002`
- ✅ Puerto 9092 accesible desde la red
- ✅ Base de datos: `ev_charging.db`

### PC1 (Driver - OTRO PC)
- ⚠️ Actualmente ejecutándose en Docker (con problemas de red)
- ✅ **SOLUCIÓN**: Ejecutar con Python directamente

## 🚀 Pasos para PC1 (Driver)

### 1. Copiar archivos del proyecto

Copia toda la carpeta `SD` al PC del Driver.

### 2. Instalar dependencias

```powershell
cd SD
pip install kafka-python websockets aiohttp
```

### 3. Verificar network_config.py

Asegúrate de que tenga:
```python
PC2_IP = "172.20.10.8"  # IP del Central
KAFKA_BROKER = "172.20.10.8:9092"
```

### 4. Copiar base de datos (OPCIONAL)

```powershell
# Copiar desde PC2 (Central) a PC1 (Driver)
# O crear una nueva con:
cd SD
python database.py init
```

### 5. Ejecutar el Driver

```powershell
cd SD/EV_Driver
python EV_Driver_WebSocket.py
```

Deberías ver:
```
📡 Kafka Broker:     172.20.10.8:9092
✅ Kafka producer and consumer initialized
```

### 6. Acceder al Dashboard

Abre: http://localhost:8001

## 🧪 Probar el Flujo

1. **Login**: `driver1` / `pass123`
2. **Solicitar Carga**: Click en el botón
3. **Verificar**:
   - ✅ Deberías ver "Carga iniciada en CP_XXX"
   - ✅ El CP cambia de "reserved" a "charging" automáticamente

## 📊 Monitorear el Flujo

En el **PC del Central** (este PC):

```powershell
docker logs ev-central -f
```

**Salida esperada cuando el Driver solicite carga:**

```
[CENTRAL] 🔐 Solicitud de autorización: usuario=driver1, buscando CP disponible...
[CENTRAL] 🎯 CP CP_001 asignado y reservado automáticamente para driver1
[CENTRAL] 📨 Received event: charging_started from topic: driver-events
[CENTRAL] ⚡ Suministro iniciado - Sesión 5 en CP CP_001 para usuario driver1
```

## ❌ Si no funciona

### Error: "Sistema de mensajería no disponible"

1. Verificar que Kafka esté accesible:
   ```powershell
   Test-NetConnection -ComputerName 172.20.10.8 -Port 9092
   ```

2. Si falla, verifica el firewall del Central (PC2):
   ```powershell
   # En PC2 (Central)
   New-NetFirewallRule -DisplayName "Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
   ```

### Error: "Kafka not available"

El producer no puede conectarse. Verifica:
- IP correcta en `network_config.py`
- Kafka corriendo en PC2
- Firewall abierto

### El CP se queda en "reserved"

Esto significa que el evento `charging_started` no llegó al Central.

**Verifica logs:**
```powershell
# En PC1 (Driver)
# Busca en los logs: "📤 Enviado evento charging_started"

# En PC2 (Central)
docker logs ev-central | Select-String "charging_started"
```

**Si NO aparece en los logs del Central**, el problema es:
1. Kafka no está escuchando desde el exterior
2. Firewall bloqueando
3. IP incorrecta

**Solución**: Ejecutar el Driver con Python (NO con Docker) resuelve todos estos problemas.

## 📝 Credenciales

```
driver1 / pass123    Balance: €150.00
driver2 / pass456    Balance: €200.00
maria_garcia / maria2025  Balance: €180.00
```

## 🔗 URLs Importantes

- **Driver Dashboard**: http://localhost:8001
- **Central Admin**: http://172.20.10.8:8002
- **Kafka UI**: http://172.20.10.8:8080

## ✅ Checklist Final

Antes de solicitar carga, verifica:

- [ ] Kafka corriendo en PC2: `docker ps | findstr kafka`
- [ ] Central corriendo en PC2: `docker ps | findstr central`
- [ ] Firewall puerto 9092 abierto en PC2
- [ ] network_config.py con IP correcta (172.20.10.8)
- [ ] Dependencias instaladas en PC1: `pip install kafka-python websockets aiohttp`
- [ ] Driver ejecutándose: `python EV_Driver_WebSocket.py`

## 🎉 Si todo está OK

Cuando el Driver solicite carga:
1. Central asigna CP automáticamente ✅
2. CP se marca como "reserved" ✅
3. Central recibe charging_started ✅
4. CP cambia a "charging" ✅
5. Sesión registrada en BD ✅

**¡FLUJO COMPLETO FUNCIONANDO!** 🚀


