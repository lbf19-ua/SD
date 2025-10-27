# 📊 Estados de CP según el PDF

Según **Practica_SD2526_EVCharging_V2.pdf**:

## Estados Correctos:

1. **Activado (disponible)**: VERDE
   - CP funcionando y esperando solicitud
   - Estado BD: `available`

2. **Parado (fuera de servicio)**: NARANJA "Out of Order"
   - CP correcto pero bloqueado por Central
   - Estado BD: `out_of_service`

3. **Suministrando**: VERDE con datos
   - CP funcionando y cargando vehículo
   - Muestra: Consumo kW, Importe €, ID conductor
   - Estado BD: `charging`

4. **Averiado**: ROJO
   - CP conectado pero con avería
   - Estado BD: `fault`

5. **Desconectado**: GRIS
   - CP no conectado al sistema
   - Estado BD: `offline`

## ⚠️ Regla Importante:

**Central DEBE poder asignar carga a CPs en estado `offline` (Desconectado)**

Solo rechaza si está en:
- `fault` (Averiado)
- `out_of_service` (Fuera de servicio)

