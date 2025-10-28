# Configuración del Driver en OTRO PC

## Situación
- **Este PC (Central)**: 172.20.10.8 - Corriendo Kafka y Central
- **Otro PC (Driver)**: Necesita conectarse al Central

## Archivos a actualizar en el PC del Driver

### 1. `network_config.py`

Asegúrate de que tenga estas IPs:

```python
# PC1 - EV_Driver (Interfaz de conductor) - TU IP LOCAL
PC1_IP = "TU_IP_LOCAL_AQUI"

# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "172.20.10.8"  # ✅ IP DEL CENTRAL

# PC3 - EV_CP (Monitor & Engine - Punto de carga)
PC3_IP = "TU_IP_LOCAL_AQUI"
```

### 2. `docker-compose.pc1.yml`

Asegúrate de que tenga estas variables de entorno:

```yaml
environment:
  # Kafka broker está en PC2 (EL OTRO PC - 172.20.10.8)
  - KAFKA_BROKER=172.20.10.8:9092  # ✅ CAMBIAR AQUÍ
  - CENTRAL_IP=172.20.10.8         # ✅ CAMBIAR AQUÍ
  - WS_PORT=8001
  - PYTHONUNBUFFERED=1
```

### 3. Verificar conectividad

Antes de iniciar el Driver, verifica que puedas alcanzar el Central:

```powershell
# Desde el PC del Driver, prueba:
ping 172.20.10.8
Test-NetConnection -ComputerName 172.20.10.8 -Port 9092
```

## Instrucciones

### En el PC del Driver:

1. **Edita `network_config.py`**:
   - Cambia `PC2_IP` a `172.20.10.8`

2. **Edita `docker-compose.pc1.yml`**:
   - Cambia `KAFKA_BROKER` a `172.20.10.8:9092`
   - Cambia `CENTRAL_IP` a `172.20.10.8`

3. **Reinicia el Driver**:
   ```powershell
   docker-compose -f docker-compose.pc1.yml down
   docker-compose -f docker-compose.pc1.yml up -d
   ```

4. **Verifica los logs**:
   ```powershell
   docker logs ev-driver -f
   ```
   
   Deberías ver:
   ```
   [DRIVER] ✅ Kafka producer and consumer initialized
   📡 Kafka Broker: 172.20.10.8:9092
   ```

5. **Prueba la conexión**:
   - Abre http://localhost:8001
   - Login: driver1 / pass123
   - Solicita carga
   - Debería funcionar ✅

## Solución rápida

Si quieres una solución rápida, solo actualiza estas dos líneas en los archivos:

```bash
# Buscar y reemplazar:
# 192.168.1.235 → 172.20.10.8
```

En:
- `network_config.py` (línea PC2_IP)
- `docker-compose.pc1.yml` (líneas KAFKA_BROKER y CENTRAL_IP)


