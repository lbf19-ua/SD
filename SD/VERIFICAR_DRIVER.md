# 🔍 Verificar Driver en el Otro PC

## Problema: CP se queda en "reserved"

El CP está `reserved` pero no pasa a `charging` porque **Driver no está creando la sesión**.

## Diagnóstico en el Otro PC

**Ejecuta esto en el otro PC:**

```powershell
# 1. Ver logs recientes de Driver
docker logs ev-driver --tail=100

# 2. Buscar estos mensajes específicos:
docker logs ev-driver | Select-String -Pattern "Central autorizó|Received.*AUTHORIZATION_RESPONSE|create_charging_session|Session created"

# 3. Verificar que Driver está escuchando Kafka
docker logs ev-driver | Select-String -Pattern "Consumer started|Kafka.*available"
```

## Posibles Causas

### Causa 1: Driver no recibe la respuesta

**Síntoma:** No aparece "✅ Central autorizó carga en CP_001"

**Solución:**
- Verificar que Driver esté escuchando el topic `central-events`
- Verificar conectividad Kafka UI: http://192.168.1.235:8080
- Ver si hay mensajes en `central-events`

### Causa 2: Driver recibe pero websocket es None

**Síntoma:** Aparece "Central autorizó" pero no se crea sesión

**Causa:** La línea 101 en EV_Driver_WebSocket.py muestra `ws = auth_data.get('websocket')`, si es None no puede notificar al cliente

**Solución:** Verificar que el websocket esté conectado cuando se solicita la carga

### Causa 3: Error al crear sesión en BD

**Síntoma:** Aparece error al llamar a `create_charging_session`

**Verificar:**
```powershell
docker logs ev-driver | Select-String -Pattern "Error|Exception|Traceback"
```

## Test Rápido

**En el otro PC, intenta solicitar carga de nuevo y luego:**

```powershell
# Ver los logs completos
docker logs ev-driver --tail=200

# Comparte los logs aquí para que vea exactamente qué está pasando
```

