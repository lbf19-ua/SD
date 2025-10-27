# 🔍 Problema: CP se queda en estado "reserved"

## 📊 Estado Actual

Según la imagen del dashboard:
- ✅ CP_001 está en estado "reserved"
- ❌ No hay sesiones activas
- ❌ El estado NO cambia a "charging"

## 🎯 Lo que DEBERÍA pasar

Después de que Central autoriza (`authorized: True`):

1. **Central** → Marca CP como `reserved` ✅ (funciona)
2. **Driver** → Recibe `AUTHORIZATION_RESPONSE` con `authorized: True`
3. **Driver** → Crea sesión de carga (`create_charging_session`)
4. **BD** → CP cambia de `reserved` a `charging`
5. **Dashboard** → Muestra sesión activa con datos en tiempo real

## ⚠️ Problema Detectado

**El Driver NO está creando la sesión de carga.**

Posibles causas:
1. Driver no recibe `AUTHORIZATION_RESPONSE` de Central
2. Driver recibe pero no procesa correctamente
3. Driver intenta crear sesión pero falla

## 🔧 Solución

**Verificar en el otro PC (Driver):**

```powershell
# Ver logs de Driver
docker logs ev-driver --tail=50

# Buscar estos mensajes:
# - "✅ Central autorizó carga en CP_001"
# - "Session created: X"
# - Algún error relacionado con create_charging_session
```

**Si NO aparecen esos mensajes:**
- Driver no está recibiendo la respuesta
- Verificar que Driver esté escuchando el topic `central-events`
- Verificar que Kafka entregue los mensajes correctamente

