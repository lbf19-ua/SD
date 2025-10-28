# Cambios para aplicar en PC2 (Central)

## Problema
Central en PC2 no puede conectarse a Kafka y no está respondiendo a las peticiones de autorización del Driver.

## Cambios aplicados en PC1

### 1. `SD/EV_Central/EV_Central_WebSocket.py` (línea 263-279)

Se corrigió la función `publish_event()` para que publique en `central-events` con el formato correcto:

```python
def publish_event(self, event_type, data):
    """Publica un evento en Kafka"""
    if self.producer:
        try:
            # Mezclar event_type y data en el mismo evento
            event = {
                'message_id': generate_message_id(),
                'event_type': event_type,
                **data,  # Incluir todos los datos directamente
                'timestamp': current_timestamp()
            }
            # Publicar en central-events para que lo reciban Drivers y Monitors
            self.producer.send('central-events', event)
            self.producer.flush()
            print(f"[CENTRAL] 📤 Published {event_type} to central-events: {data}")
        except Exception as e:
            print(f"[CENTRAL] ⚠️  Failed to publish event: {e}")
```

## Pasos para aplicar en PC2

1. **Copiar el archivo actualizado:**
   ```powershell
   # En PC2
   # Copiar SD/EV_Central/EV_Central_WebSocket.py con los cambios
   ```

2. **Reconstruir y reiniciar Central:**
   ```powershell
   docker-compose -f docker-compose.pc2.yml down
   docker-compose -f docker-compose.pc2.yml up -d --build
   ```

3. **Verificar que se conecta a Kafka:**
   ```powershell
   docker logs ev-central --tail 30
   # Deberías ver: "[CENTRAL] ✅ Kafka producer initialized"
   ```

4. **Probar la autorización:**
   - Ir a la interfaz del Driver en PC1: http://192.168.1.228:8001
   - Hacer login como driver1/pass123
   - Click en "Solicitar Carga"
   - Debería recibir respuesta de Central vía Kafka




