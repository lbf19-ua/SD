# 🚀 Instrucciones Finales - Resolver el Problema de Autorización

## 📍 Estado Actual

✅ **Driver (PC1 - tu PC actual)**: Modificado y funcionando  
❌ **Central (PC2)**: Necesita reconstruirse con los cambios

## 🎯 Lo que tienes que hacer

### En PC2 (donde corre Central + Kafka)

1. **Conectar a PC2** (por SSH, escritorio remoto, o físicamente)

2. **Copiar el archivo actualizado:**
   - Ve a: `C:\Users\luisb\Desktop\SD_Final\SD\SD\EV_Central\EV_Central_WebSocket.py`
   - Cópialo a PC2 en la misma ubicación

3. **Reconstruir y reiniciar Central:**
   ```powershell
   cd C:\Users\[TU_USUARIO]\Desktop\SD_Final\SD\SD
   
   # Reconstruir y reiniciar Central
   docker-compose -f docker-compose.pc2.yml down
   docker-compose -f docker-compose.pc2.yml up -d --build
   ```

4. **Verificar que funciona:**
   ```powershell
   # Ver logs de Central
   docker logs ev-central --tail 30
   
   # Deberías ver:
   # "[CENTRAL] ✅ Kafka producer initialized"
   # "[KAFKA] 📡 Consumer started, listening to ['driver-events', 'cp-events']"
   ```

### En PC1 (tu PC actual - donde estás ahora)

**No necesitas hacer nada más.** El Driver ya está configurado correctamente.

## ✅ Probar el Sistema

1. **Abrir la interfaz del Driver:**
   - Ir a: http://localhost:8001 (o http://192.168.1.228:8001)
   - Login: `driver1` / `pass123`

2. **Solicitar carga:**
   - Click en "Solicitar Carga"
   - Deberías ver: "Esperando autorización de Central..."
   - Después de unos segundos, deberías recibir la respuesta

3. **Verificar en logs:**
   ```powershell
   # En PC1 (Driver)
   docker logs ev-driver --tail 20
   
   # Deberías ver:
   # "[DRIVER] ✅ Central autorizó carga en CP_001"
   
   # En PC2 (Central)
   docker logs ev-central --tail 20
   
   # Deberías ver:
   # "[CENTRAL] 📤 Published AUTHORIZATION_RESPONSE to central-events"
   ```

## 📊 Flujo Completo

```
Driver (PC1)              Kafka              Central (PC2)
    |                      |                     |
    |-- AUTHORIZATION     -->|                     |
    |    REQUEST           |                     |
    |                      |--->|                 |
    |                      |    |                 |
    |                      |    |-- Validar CP en BD
    |                      |    |-- Reservar CP
    |                      |    |-- Publicar
    |                      |<---|    respuesta
    |<---------------------|                     |
    |-- AUTHORIZATION      |                     |
    |   RESPONSE           |                     |
    |                      |                     |
    |-- Crear sesión       |                     |
    |-- Notificar cliente  |                     |
```

## 🐛 Si sigue sin funcionar

### Revisar conectividad Kafka
```powershell
# En PC1, verificar que puedes conectar a Kafka en PC2
Test-NetConnection 192.168.1.235 -Port 9092

# Debe responder: "TcpTestSucceeded: True"
```

### Revisar logs
```powershell
# Central (PC2)
docker logs ev-central --tail 100

# Driver (PC1)
docker logs ev-driver --tail 100
```

### Verificar que Central está escuchando en driver-events
```powershell
# En PC2
docker exec ev-kafka-ui curl http://localhost:8080/api/clusters/ev-charging-cluster/topics/driver-events

# O abrir: http://192.168.1.235:8080
# Buscar el topic "driver-events"
# Verificar que hay mensajes llegando
```

## ✨ Resultado Esperado

Cuando funcionen los cambios, verás:
- Driver envía solicitud → "Esperando autorización..."
- Central procesa → "✅ CP reservado para cliente"
- Central responde → Autorización enviada a Kafka
- Driver recibe respuesta → "✅ Central autorizó carga"
- Interfaz actualiza → Muestra sesión activa

¡Y tendrás el sistema funcionando con la arquitectura correcta! 🎉




