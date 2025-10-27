# 🚨 Diagnóstico Urgente: Driver no comunica con Central

## 🔍 Pruebas Inmediatas en el PC de Driver

### 1. Verifica que Driver está corriendo:
```powershell
docker ps
# Debe mostrar ev-driver con STATUS = "Up"
```

### 2. Ver los logs de Driver:
```powershell
docker logs ev-driver --tail=50
```

**Busca estos mensajes:**
- ✅ `[DRIVER] ✅ Kafka producer and consumer initialized`
- ✅ `[KAFKA] 📡 Consumer started, listening to...`
- ❌ `[KAFKA] ⚠️ Warning: Kafka not available`

### 3. Verifica la configuración de red en Driver:

```powershell
# Ver network_config.py
cat network_config.py | Select-String "PC2_IP"
# Debe mostrar: PC2_IP = "192.168.1.235"
```

### 4. Prueba conectividad desde Driver a Kafka:
```powershell
# Desde el PC donde corre Driver:
Test-NetConnection 192.168.1.235 -Port 9092
```

**Salida esperada**: `TcpTestSucceeded : True`

---

## 🔧 Soluciones Comunes

### Problema 1: Network config incorrecta

**Síntoma**: Driver dice "Kafka not available"
**Solución**:
1. Edita `SD/network_config.py` en el PC de Driver
2. Cambia `PC2_IP = "TU_IP_ANTERIOR"` → `PC2_IP = "192.168.1.235"`
3. Reinicia Driver:
   ```powershell
   docker-compose -f docker-compose.pc1.yml down
   docker-compose -f docker-compose.pc1.yml up -d
   ```

### Problema 2: Firewall bloquea Kafka

**Síntoma**: `Test-NetConnection` falla
**Solución**:
```powershell
# En el PC de Driver, como Admin:
New-NetFirewallRule -DisplayName "EV Kafka" -Direction Outbound -RemotePort 9092 -Protocol TCP -Action Allow
```

### Problema 3: Driver usa KAFKA_BROKER incorrecto

**Síntoma**: Logs muestran "NoBrokersAvailable"
**Solución**:
```powershell
# En el PC de Driver:
docker exec ev-driver python -c "from network_config import KAFKA_BROKER; print(KAFKA_BROKER)"
# Debe imprimir: 192.168.1.235:9092
```

---

## 📊 Flujo Correcto

```
1. Driver recibe "Start Charging" del usuario
   ↓
2. Driver valida usuario localmente
   ↓
3. Driver envía evento a Kafka topic 'driver-events':
   {
     "event_type": "AUTHORIZATION_REQUEST",
     "username": "user1",
     "cp_id": "CP01",
     "client_id": "abc123"
   }
   ↓
4. Central recibe evento de Kafka
   ↓
5. Central valida en BD y responde
   ↓
6. Driver recibe AUTHORIZATION_RESPONSE
   ↓
7. Driver inicia carga o muestra error
```

---

## 🎯 Acciones Inmediatas

**Ejecuta esto en el PC de Driver y compárteme el output:**

```powershell
# 1. Estado de contenedores
docker ps

# 2. Logs recientes de Driver
docker logs ev-driver --tail=30

# 3. Config de red
cat SD/network_config.py | Select-String -Pattern "PC2_IP|KAFKA_BROKER"

# 4. Conectividad
Test-NetConnection 192.168.1.235 -Port 9092
```

**Con esos 4 outputs puedo diagnosticar exactamente qué está fallando.**

