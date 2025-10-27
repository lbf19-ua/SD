# ✅ Arquitectura Correcta

## 📋 Principio Fundamental

**SOLO CENTRAL modifica la base de datos.**

Driver y Monitor solo:
- Lee datos de la BD (para mostrar estado actual)
- Envía eventos a Kafka
- NUNCA crean/modifican sesiones o estados en la BD

## 🔄 Flujo Correcto

### 1. Solicitud de Carga (Driver → Central)

```
Driver solicita carga:
├─ Verifica usuario local (balance, sesión activa)
├─ Envía AUTHORIZATION_REQUEST a Kafka
└─ Espera respuesta de Central
```

### 2. Autorización (Central)

```
Central recibe AUTHORIZATION_REQUEST:
├─ Verifica CP existe en BD
├─ Verifica estado del CP (no debe estar fault o out_of_service)
├─ Reserva el CP (estado: reserved)
└─ Responde AUTHORIZATION_RESPONSE (authorized: True/False)
```

### 3. Inicio de Carga (Driver → Central)

```
Driver recibe authorized: True:
├─ NO crea sesión en BD ❌
├─ Envía evento charging_started a Kafka
└─ Actualiza solo su estado local (memoria)
```

### 4. Creación de Sesión (Central)

```
Central recibe charging_started:
├─ Crea sesión en BD: db.create_charging_session()
├─ Actualiza CP a estado 'charging'
├─ Guarda sesión activa en BD
└─ Dashboard muestra sesión activa
```

## ⚠️ Cambios Realizados

### En Driver (EV_Driver_WebSocket.py):
- ❌ Eliminado: `db.create_charging_session()` 
- ✅ Agregado: Envío de evento `charging_started` a Kafka
- ✅ Ahora solo Central crea sesiones en BD

### En Central (EV_Central_WebSocket.py):
- ✅ Procesa evento `charging_started` y crea sesión en BD
- ✅ Solo rechaza CPs en estado `fault` o `out_of_service`
- ✅ Permite CPs en estado `offline` y `available`

## 🎯 Estados de CP Correctos

Según PDF:
- **Activado (available)**: ✅ Permite carga
- **Desconectado (offline)**: ✅ Permite carga (hasta que conecte)
- **Suministrando (charging)**: Solo se asigna
- **Averiado (fault)**: ❌ Rechaza carga
- **Fuera de servicio (out_of_service)**: ❌ Rechaza carga

## 📊 Inicialización de Central

Al iniciar Central:
1. Termina sesiones activas previas
2. Marca TODOS los CPs como `offline` (desconectados)
3. Muestra CPs en dashboard con estado `offline` (gris)
4. Cuando un CP conecta, se actualiza su estado

## 🧪 Test

**Desde Driver (otro PC):**
1. Solicita carga → Central autoriza
2. Driver envía `charging_started` → Central crea sesión
3. **Dashboard de Central debe mostrar:**
   - CP_001 en estado "charging" (verde)
   - Sesión activa con usuario y datos

